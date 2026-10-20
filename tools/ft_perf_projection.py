"""Experimental, pure-graph ONNX helper for the pinned YOLOX-s model.

This is NOT a general detector conversion tool and makes no claim about
speed or accuracy. ``ft_count._decode_yolox`` reads only the box
coordinates (columns 0:4) and the person score (``column4 * column5``)
from the raw [1, 8400, 85] model output; it never touches the other 79
class columns. ``project_person_output`` appends a pure-graph ``Slice``
that narrows the model's declared output from [1, 8400, 85] to
[1, 8400, 6] (coords + obj + person score), so a caller can carry less
data out of the model without changing any existing node, weight, batch
size, precision, or original serialization. The caller is responsible
for verifying pinned model identity and comparing numerical
outputs/events against the original, unmodified model file.

``make_two_crop_batch`` is a separate, experimental pure-graph helper
that rebatches the pinned model's three head ``Reshape`` nodes so a
caller can run two *separate* existing crops as one batch-2 input
instead of two batch-1 calls; it never produces a merged/union crop
and the caller must still verify per-item parity against batch-1 runs.

No ``onnx`` import happens at module import time: every function here
takes the already-imported ``onnx`` module as its first argument.
"""
from __future__ import annotations

EXPECTED_INPUT_SHAPE = (1, 3, 640, 640)
EXPECTED_OUTPUT_SHAPE = (1, 8400, 85)
PROJECTED_OUTPUT_SHAPE = (1, 8400, 6)
MIN_OPSET_VERSION = 10
STANDARD_DOMAINS = ("", "ai.onnx")
HEAD_RESHAPE_SHAPE_VALUE = (1, 85, -1)
HEAD_RESHAPE_BATCH_FROM_INPUT_VALUE = (0, 85, -1)
EXPECTED_HEAD_RESHAPE_COUNT = 3


class ProjectionValidationError(ValueError):
    """Raised when a model does not match the single supported shape contract."""


def _static_shape(tensor_type):
    dims = tensor_type.shape.dim
    shape = []
    for dim in dims:
        if dim.WhichOneof("value") != "dim_value":
            return None
        shape.append(dim.dim_value)
    return tuple(shape)


def _require_opset_version(onnx_module, model):
    versions = set()
    for opset in model.opset_import:
        if opset.domain in STANDARD_DOMAINS:
            versions.add(opset.version)
    if not versions:
        raise ProjectionValidationError("model is missing a standard ONNX opset_import entry")
    if len(versions) > 1:
        raise ProjectionValidationError("model has conflicting standard ONNX opset_import versions")
    version = next(iter(versions))
    if version < MIN_OPSET_VERSION:
        raise ProjectionValidationError(
            f"model opset version {version} is below the required minimum {MIN_OPSET_VERSION}"
        )


def _require_no_external_initializers(onnx_module, model):
    for initializer in model.graph.initializer:
        if initializer.data_location == onnx_module.TensorProto.EXTERNAL:
            raise ProjectionValidationError(
                f"initializer {initializer.name!r} uses external data, which is not supported"
            )


def _require_single_input(onnx_module, model):
    initializer_names = {t.name for t in model.graph.initializer}
    real_inputs = [i for i in model.graph.input if i.name not in initializer_names]
    if len(real_inputs) != 1:
        raise ProjectionValidationError("model must have exactly one non-initializer graph input")
    tensor_type = real_inputs[0].type.tensor_type
    if tensor_type.elem_type != onnx_module.TensorProto.FLOAT:
        raise ProjectionValidationError("model input must be FLOAT")
    shape = _static_shape(tensor_type)
    if shape != EXPECTED_INPUT_SHAPE:
        raise ProjectionValidationError(
            f"model input must have static shape {EXPECTED_INPUT_SHAPE}, got {shape}"
        )
    return real_inputs[0]


def _require_single_output(onnx_module, model):
    if len(model.graph.output) != 1:
        raise ProjectionValidationError("model must have exactly one graph output")
    output = model.graph.output[0]
    tensor_type = output.type.tensor_type
    if tensor_type.elem_type != onnx_module.TensorProto.FLOAT:
        raise ProjectionValidationError("model output must be FLOAT")
    shape = _static_shape(tensor_type)
    if shape != EXPECTED_OUTPUT_SHAPE:
        raise ProjectionValidationError(
            f"model output must have static shape {EXPECTED_OUTPUT_SHAPE}, got {shape}"
        )
    return output


def _collect_existing_names(model):
    names = set()
    for value_info in model.graph.input:
        names.add(value_info.name)
    for value_info in model.graph.output:
        names.add(value_info.name)
    for value_info in model.graph.value_info:
        names.add(value_info.name)
    for initializer in model.graph.initializer:
        names.add(initializer.name)
    for node in model.graph.node:
        if node.name:
            names.add(node.name)
        names.update(node.input)
        names.update(node.output)
    return names


def _choose_prefix(existing_names):
    suffixes = ("_slice_node", "_slice_output", "_start", "_end", "_axis", "_step")
    counter = 0
    while True:
        candidate = "ft_perf_proj" if counter == 0 else f"ft_perf_proj_{counter}"
        if all((candidate + suffix) not in existing_names for suffix in suffixes):
            return candidate
        counter += 1


def project_person_output(onnx_module, model):
    """Return an in-memory copy of ``model`` with a narrowed [1, 8400, 6] output.

    ``model`` is never mutated. The returned copy keeps every existing
    node, initializer, input, and the original output's producing node
    untouched; it only appends one ``Slice`` node (plus its int64
    initializers) and replaces the graph's single declared output with
    the sliced [1, 8400, 6] FLOAT tensor. Raises
    ``ProjectionValidationError`` if ``model`` does not match the single
    supported shape/opset/domain/initializer-locality contract for the
    pinned YOLOX-s model this helper targets.
    """
    _require_opset_version(onnx_module, model)
    _require_no_external_initializers(onnx_module, model)
    _require_single_input(onnx_module, model)
    output = _require_single_output(onnx_module, model)
    original_output_name = output.name

    existing_names = _collect_existing_names(model)
    prefix = _choose_prefix(existing_names)
    slice_node_name = f"{prefix}_slice_node"
    sliced_output_name = f"{prefix}_slice_output"
    start_name = f"{prefix}_start"
    end_name = f"{prefix}_end"
    axis_name = f"{prefix}_axis"
    step_name = f"{prefix}_step"

    copy = onnx_module.ModelProto()
    copy.CopyFrom(model)

    start_init = onnx_module.helper.make_tensor(start_name, onnx_module.TensorProto.INT64, [1], [0])
    end_init = onnx_module.helper.make_tensor(end_name, onnx_module.TensorProto.INT64, [1], [6])
    axis_init = onnx_module.helper.make_tensor(axis_name, onnx_module.TensorProto.INT64, [1], [2])
    step_init = onnx_module.helper.make_tensor(step_name, onnx_module.TensorProto.INT64, [1], [1])
    copy.graph.initializer.extend([start_init, end_init, axis_init, step_init])

    slice_node = onnx_module.helper.make_node(
        "Slice",
        inputs=[original_output_name, start_name, end_name, axis_name, step_name],
        outputs=[sliced_output_name],
        name=slice_node_name,
    )
    copy.graph.node.append(slice_node)

    new_output = onnx_module.helper.make_tensor_value_info(
        sliced_output_name, onnx_module.TensorProto.FLOAT, list(PROJECTED_OUTPUT_SHAPE)
    )
    del copy.graph.output[:]
    copy.graph.output.append(new_output)

    onnx_module.checker.check_model(copy)

    return copy


def _require_three_head_reshapes(onnx_module, model):
    """Return the three (node, shape_initializer_name) head Reshape pairs.

    Each of the model's Reshape nodes must take its shape from its own,
    unshared INT64[3] initializer containing exactly
    ``HEAD_RESHAPE_SHAPE_VALUE``; anything shared, dynamic, wrongly
    shaped, or not exactly three such nodes is rejected.
    """
    initializer_by_name = {t.name: t for t in model.graph.initializer}
    reshape_nodes = [n for n in model.graph.node if n.op_type == "Reshape"]
    if len(reshape_nodes) != EXPECTED_HEAD_RESHAPE_COUNT:
        raise ProjectionValidationError(
            f"model must have exactly {EXPECTED_HEAD_RESHAPE_COUNT} Reshape nodes, "
            f"found {len(reshape_nodes)}"
        )

    consumer_counts = {}
    for node in model.graph.node:
        for name in node.input:
            consumer_counts[name] = consumer_counts.get(name, 0) + 1

    seen_shape_names = set()
    shape_infos = []
    for node in reshape_nodes:
        if node.domain not in STANDARD_DOMAINS or any(
                attr.name == "allowzero" and attr.i != 0 for attr in node.attribute):
            raise ProjectionValidationError("head Reshape must copy zero-valued dimensions")
        if len(node.input) < 2 or not node.input[1]:
            raise ProjectionValidationError(
                f"Reshape node {node.name!r} must take its shape from a second input"
            )
        shape_name = node.input[1]
        if shape_name not in initializer_by_name:
            raise ProjectionValidationError(
                f"Reshape node {node.name!r} shape input {shape_name!r} must be a graph initializer"
            )
        if shape_name in seen_shape_names:
            raise ProjectionValidationError(
                f"Reshape shape initializer {shape_name!r} is shared by more than one Reshape node"
            )
        seen_shape_names.add(shape_name)
        if consumer_counts.get(shape_name, 0) != 1:
            raise ProjectionValidationError(
                f"Reshape shape initializer {shape_name!r} must be consumed only by its own Reshape node"
            )
        initializer = initializer_by_name[shape_name]
        if initializer.data_type != onnx_module.TensorProto.INT64:
            raise ProjectionValidationError(
                f"Reshape shape initializer {shape_name!r} must be INT64"
            )
        if list(initializer.dims) != [len(HEAD_RESHAPE_SHAPE_VALUE)]:
            raise ProjectionValidationError(
                f"Reshape shape initializer {shape_name!r} must have shape "
                f"[{len(HEAD_RESHAPE_SHAPE_VALUE)}]"
            )
        values = list(onnx_module.numpy_helper.to_array(initializer))
        if values != list(HEAD_RESHAPE_SHAPE_VALUE):
            raise ProjectionValidationError(
                f"Reshape shape initializer {shape_name!r} must contain "
                f"{list(HEAD_RESHAPE_SHAPE_VALUE)}, got {values}"
            )
        shape_infos.append((node, shape_name))

    return shape_infos


def make_two_crop_batch(onnx_module, model, person_output=False):
    """Return an in-memory copy of ``model`` rebatched to carry two crops.

    ``model`` is never mutated. This targets the pinned YOLOX-s model's
    exact three head ``Reshape`` nodes (each reshaping a per-scale
    feature map to ``[1, 85, -1]`` from its own, unshared INT64[3]
    initializer): each such initializer's value is changed to
    ``[0, 85, -1]`` so ONNX's Reshape copies the batch dimension from
    its input instead of hardcoding it to 1. The model's sole real input
    and sole declared output batch dimension are then changed from 1 to
    2, stale ``value_info`` shape annotations are dropped, and shape
    inference plus the ONNX checker rebuild and validate available shapes.

    No existing computation node or weight is altered other than the
    three head Reshape shape initializers. If ``person_output`` is
    True, ``project_person_output`` is applied to the original model
    first, so the returned model's output is ``[2, 8400, 6]`` instead
    of ``[2, 8400, 85]``.

    This is an experimental, pure-graph derivation: the two batch items
    are two *separate* existing crops carried in one batch, never a
    merged/union crop. The caller is responsible for pinning model
    identity and comparing each batch item's output against separate
    batch-1 runs before relying on this helper.
    """
    if type(person_output) is not bool:
        raise ProjectionValidationError("person_output must be a bool")

    _require_opset_version(onnx_module, model)
    _require_no_external_initializers(onnx_module, model)
    _require_single_input(onnx_module, model)
    _require_single_output(onnx_module, model)
    shape_infos = _require_three_head_reshapes(onnx_module, model)
    shape_names = {name for _, name in shape_infos}

    if person_output:
        source = project_person_output(onnx_module, model)
    else:
        source = onnx_module.ModelProto()
        source.CopyFrom(model)

    real_input = _require_single_input(onnx_module, source)

    initializer_by_name = {t.name: t for t in source.graph.initializer}
    for shape_name in shape_names:
        initializer = initializer_by_name[shape_name]
        new_tensor = onnx_module.helper.make_tensor(
            initializer.name,
            initializer.data_type,
            list(initializer.dims),
            list(HEAD_RESHAPE_BATCH_FROM_INPUT_VALUE),
        )
        initializer.CopyFrom(new_tensor)

    real_input.type.tensor_type.shape.dim[0].dim_value = 2
    source.graph.output[0].type.tensor_type.shape.dim[0].dim_value = 2

    del source.graph.value_info[:]

    inferred = onnx_module.shape_inference.infer_shapes(source, data_prop=True)
    onnx_module.checker.check_model(inferred)

    return inferred
