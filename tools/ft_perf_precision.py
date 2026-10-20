"""Experimental, pure-graph ONNX FP16 conversion helper for the pinned YOLOX-s model.

This is NOT a general FP16 converter and makes no accuracy claim: FP16
is lossy (rounding and possible underflow of small magnitudes), so the
returned model is explicitly an *approximate* numerical variant of the
original, not a parity-preserving one. The caller is responsible for
pinning model identity and comparing numerical outputs/events against
the original, unmodified FP32 model before relying on this helper.

No ``onnx`` or ``numpy`` import happens at module import time: every
function here takes the already-imported ``onnx`` module as its first
argument, and ``numpy`` (only needed for tensor value checks) is
imported lazily inside ``make_fp16_model``. The FP16 conversion itself
is delegated to an injected ``converter`` callable (normally
``onnxruntime.transformers.float16.convert_float_to_float16``); this
module never imports ``onnxruntime``.
"""
from __future__ import annotations

import math

EXPECTED_INPUT_RANK = 4
SUPPORTED_BATCH_SIZES = (1, 2)
INPUT_CHANNELS = 3
INPUT_SIZE = 640
NUM_ANCHORS = 8400
SUPPORTED_OUTPUT_COLUMNS = (6, 85)
STANDARD_DOMAINS = ("", "ai.onnx")
MAX_FINITE_VALUE = 65504.0

# Versioned, numeric-only conversion policy. Exported so a caller can bind
# its own identity/provenance records to the exact settings used here,
# without re-deriving them. Values other than "version" are passed
# directly as keyword arguments to the injected converter; do not mutate
# this dict.
CONVERSION_POLICY = {
    "version": 2,
    "keep_io_types": True,
    "min_positive_val": 5.96e-08,
    "max_finite_val": MAX_FINITE_VALUE,
    "disable_shape_infer": False,
}


class PrecisionValidationError(ValueError):
    """Raised when a model or converter result does not match the supported FP16 contract."""


def _static_shape(tensor_type):
    shape = []
    for dim in tensor_type.shape.dim:
        if dim.WhichOneof("value") != "dim_value":
            return None
        shape.append(dim.dim_value)
    return tuple(shape)


def _require_standard_domains(onnx_module, model):
    for opset in model.opset_import:
        if opset.domain not in STANDARD_DOMAINS:
            raise PrecisionValidationError(f"unsupported opset domain {opset.domain!r}")
    for node in model.graph.node:
        if node.domain not in STANDARD_DOMAINS:
            raise PrecisionValidationError(f"unsupported node domain {node.domain!r}")


def _require_no_subgraphs_or_functions(onnx_module, model):
    if len(model.functions):
        raise PrecisionValidationError("model must not define any functions")
    for node in model.graph.node:
        for attr in node.attribute:
            if attr.type in (onnx_module.AttributeProto.GRAPH, onnx_module.AttributeProto.GRAPHS):
                raise PrecisionValidationError(f"node {node.name!r} must not contain a subgraph")


def _require_no_external_or_sparse_initializers(onnx_module, model):
    for tensor, _ in _iter_model_tensors(onnx_module, model):
        if tensor.data_location == onnx_module.TensorProto.EXTERNAL or tensor.external_data:
            raise PrecisionValidationError("external tensor data is unsupported")
    if len(model.graph.sparse_initializer):
        raise PrecisionValidationError("model must not use sparse initializers")
    if any(a.type in (onnx_module.AttributeProto.SPARSE_TENSOR,
                      onnx_module.AttributeProto.SPARSE_TENSORS)
           for n in model.graph.node for a in n.attribute):
        raise PrecisionValidationError("sparse tensor attributes are unsupported")


def _require_single_input(onnx_module, model):
    initializer_names = {t.name for t in model.graph.initializer}
    real_inputs = [i for i in model.graph.input if i.name not in initializer_names]
    if len(real_inputs) != 1:
        raise PrecisionValidationError("model must have exactly one non-initializer graph input")
    tensor_type = real_inputs[0].type.tensor_type
    if tensor_type.elem_type != onnx_module.TensorProto.FLOAT:
        raise PrecisionValidationError("model input must be FLOAT")
    shape = _static_shape(tensor_type)
    if shape is None or len(shape) != EXPECTED_INPUT_RANK:
        raise PrecisionValidationError("model input must have a fully static rank-4 shape")
    batch, channels, height, width = shape
    if (batch not in SUPPORTED_BATCH_SIZES or channels != INPUT_CHANNELS or
            height != INPUT_SIZE or width != INPUT_SIZE):
        raise PrecisionValidationError(
            f"model input must be [1 or 2, {INPUT_CHANNELS}, {INPUT_SIZE}, {INPUT_SIZE}], got {shape}"
        )
    return real_inputs[0], batch


def _require_single_output(onnx_module, model, batch):
    if len(model.graph.output) != 1:
        raise PrecisionValidationError("model must have exactly one graph output")
    output = model.graph.output[0]
    tensor_type = output.type.tensor_type
    if tensor_type.elem_type != onnx_module.TensorProto.FLOAT:
        raise PrecisionValidationError("model output must be FLOAT")
    shape = _static_shape(tensor_type)
    if shape is None or len(shape) != 3:
        raise PrecisionValidationError("model output must have a fully static rank-3 shape")
    out_batch, anchors, columns = shape
    if out_batch != batch or anchors != NUM_ANCHORS or columns not in SUPPORTED_OUTPUT_COLUMNS:
        raise PrecisionValidationError(
            f"model output must be [{batch}, {NUM_ANCHORS}, 6 or 85], got {shape}"
        )
    return output


def _iter_model_tensors(onnx_module, model):
    for initializer in model.graph.initializer:
        yield initializer, f"initializer {initializer.name!r}"
    for node in model.graph.node:
        for attr in node.attribute:
            if attr.type == onnx_module.AttributeProto.TENSOR:
                yield attr.t, f"node {node.name!r} attribute {attr.name!r}"
            elif attr.type == onnx_module.AttributeProto.TENSORS:
                for index, tensor in enumerate(attr.tensors):
                    yield tensor, f"node {node.name!r} attribute {attr.name!r}[{index}]"


def _require_finite_bounded_float_tensors(onnx_module, np, model):
    for tensor, context in _iter_model_tensors(onnx_module, model):
        if tensor.data_type != onnx_module.TensorProto.FLOAT:
            continue
        if tensor.data_location == onnx_module.TensorProto.EXTERNAL:
            raise PrecisionValidationError(f"{context} uses external data")
        values = onnx_module.numpy_helper.to_array(tensor)
        if values.size == 0:
            continue
        if not np.isfinite(values).all():
            raise PrecisionValidationError(f"{context} contains non-finite values")
        if float(np.abs(values).max()) > MAX_FINITE_VALUE:
            raise PrecisionValidationError(f"{context} exceeds max finite value {MAX_FINITE_VALUE}")


def _has_internal_float16_tensor(onnx_module, model):
    for initializer in model.graph.initializer:
        if initializer.data_type == onnx_module.TensorProto.FLOAT16:
            return True
    for value_info in model.graph.value_info:
        if value_info.type.tensor_type.elem_type == onnx_module.TensorProto.FLOAT16:
            return True
    for node in model.graph.node:
        if node.op_type == "Cast" and node.domain in STANDARD_DOMAINS:
            for attr in node.attribute:
                if attr.name == "to" and attr.i == onnx_module.TensorProto.FLOAT16:
                    return True
    return False


def _require_no_nonfinite_weights(onnx_module, np, model):
    tensor_types = onnx_module.TensorProto
    supported = {getattr(tensor_types, name) for name in (
        "FLOAT", "FLOAT16", "BOOL", "INT8", "INT16", "INT32", "INT64",
        "UINT8", "UINT16", "UINT32", "UINT64")}
    for initializer, _ in _iter_model_tensors(onnx_module, model):
        if initializer.data_type not in supported:
            raise PrecisionValidationError("unsupported tensor dtype")
        if initializer.data_type not in (onnx_module.TensorProto.FLOAT, onnx_module.TensorProto.FLOAT16):
            continue
        if initializer.data_location == onnx_module.TensorProto.EXTERNAL:
            raise PrecisionValidationError(f"initializer {initializer.name!r} uses external data")
        values = onnx_module.numpy_helper.to_array(initializer)
        if values.size and not np.isfinite(values).all():
            raise PrecisionValidationError(f"initializer {initializer.name!r} contains non-finite values")
    for node in model.graph.node:
        for attr in node.attribute:
            values = ([attr.f] if attr.type == onnx_module.AttributeProto.FLOAT else
                      attr.floats if attr.type == onnx_module.AttributeProto.FLOATS else ())
            if not all(math.isfinite(value) for value in values):
                raise PrecisionValidationError("non-finite float attribute")

def _sort_graph(model):
    """Stable topological order for Cast nodes appended by the ORT converter."""
    available = {v.name for v in model.graph.input}
    available.update(v.name for v in model.graph.initializer)
    pending = list(model.graph.node)
    ordered = []
    while pending:
        ready = [node for node in pending if all(not name or name in available for name in node.input)]
        if not ready:
            raise PrecisionValidationError("converted graph has unresolved dependencies or a cycle")
        waiting = []
        for node in pending:
            if all(not name or name in available for name in node.input):
                for name in node.output:
                    if name and name in available:
                        raise PrecisionValidationError("converted graph has duplicate tensor definitions")
                    if name:
                        available.add(name)
                ordered.append(node)
            else:
                waiting.append(node)
        pending = waiting
    del model.graph.node[:]
    model.graph.node.extend(ordered)


def _io_contract(model):
    return tuple(tuple((v.name, v.type.tensor_type.elem_type, _static_shape(v.type.tensor_type))
                       for v in values) for values in (model.graph.input, model.graph.output))


def _check_model_or_raise(onnx_module, model):
    try:
        onnx_module.checker.check_model(model, full_check=True)
    except Exception as exc:
        raise PrecisionValidationError("model failed onnx.checker.check_model") from exc


def make_fp16_model(onnx_module, model, converter):
    """Return a separately-copied, approximate FP16-internals copy of ``model``.

    ``model`` is validated against the single supported YOLOX-s-style
    shape/schema contract (static FLOAT32 input [1 or 2, 3, 640, 640],
    static FLOAT32 output [same batch, 8400, 6 or 85], standard-domain
    ops only, no external/sparse initializers, no subgraphs/functions,
    every FLOAT tensor finite and bounded by
    ``CONVERSION_POLICY["max_finite_val"]``) and never mutated: a deep
    copy is passed to ``converter`` instead.

    ``converter`` must have the signature of
    ``onnxruntime.transformers.float16.convert_float_to_float16`` and is
    called with exactly the keyword arguments in ``CONVERSION_POLICY``.
    Its result is deep-copied again into the returned ``ModelProto`` so
    the caller never aliases either the original model or whatever
    object the converter returned/mutated.

    ORT's minimum supported nonzero clamp is ``5.96e-08``; smaller
    nonzero constants are clamped before FP16 rounding. This is an approximate numerical
    variant, not an exact-parity one. Raises ``PrecisionValidationError``
    deterministically for unsupported inputs, converter failures, or a
    malformed/non-finite/shape-changed result; it reads/writes no files
    and makes no network calls.
    """
    import numpy as np

    _require_standard_domains(onnx_module, model)
    _require_no_subgraphs_or_functions(onnx_module, model)
    _require_no_external_or_sparse_initializers(onnx_module, model)
    _require_no_nonfinite_weights(onnx_module, np, model)
    _, batch = _require_single_input(onnx_module, model)
    _require_single_output(onnx_module, model, batch)
    _require_finite_bounded_float_tensors(onnx_module, np, model)

    _check_model_or_raise(onnx_module, model)

    source = onnx_module.ModelProto()
    source.CopyFrom(model)

    converter_kwargs = {key: value for key, value in CONVERSION_POLICY.items() if key != "version"}
    try:
        converted = converter(source, **converter_kwargs)
    except Exception as exc:
        raise PrecisionValidationError("FP16 converter raised an exception") from exc

    if not isinstance(converted, onnx_module.ModelProto):
        raise PrecisionValidationError("FP16 converter must return an onnx.ModelProto")

    result = onnx_module.ModelProto()
    result.CopyFrom(converted)

    _require_standard_domains(onnx_module, result)
    _require_no_subgraphs_or_functions(onnx_module, result)
    _require_no_external_or_sparse_initializers(onnx_module, result)
    _require_no_nonfinite_weights(onnx_module, np, result)
    if _io_contract(result) != _io_contract(model):
        raise PrecisionValidationError("converted model input/output contract changed")
    _sort_graph(result)
    _check_model_or_raise(onnx_module, result)

    _, result_batch = _require_single_input(onnx_module, result)
    if result_batch != batch:
        raise PrecisionValidationError("converted model input batch size changed")
    _require_single_output(onnx_module, result, batch)

    if not _has_internal_float16_tensor(onnx_module, result):
        raise PrecisionValidationError("converted model has no internal FLOAT16 tensor")

    _require_no_nonfinite_weights(onnx_module, np, result)

    return result
