"""Tests for the experimental ft_perf_projection ONNX graph helper.

Builds small synthetic ONNX graphs (declared shapes, no huge tensor
literals) rather than loading the real pinned model. Skipped entirely
under a plain stdlib interpreter without the optional ``onnx`` package.
"""
import importlib.util
import unittest

from tools import ft_perf_projection as fpp

HAVE_ONNX = importlib.util.find_spec("onnx") is not None


def _make_base_model(onnx, opset_version=11, extra_opsets=(), output_shape=(1, 8400, 85),
                      input_shape=(1, 3, 640, 640), num_outputs=1, external_initializer=False):
    helper = onnx.helper
    TensorProto = onnx.TensorProto

    input_vi = helper.make_tensor_value_info("images", TensorProto.FLOAT, list(input_shape))

    shape_init = helper.make_tensor(
        "shape_init", TensorProto.INT64, [len(output_shape)], list(output_shape)
    )

    nodes = []
    outputs = []
    for i in range(num_outputs):
        name = "output" if i == 0 else f"output_{i}"
        outputs.append(helper.make_tensor_value_info(name, TensorProto.FLOAT, list(output_shape)))
        nodes.append(helper.make_node(
            "ConstantOfShape",
            inputs=["shape_init"],
            outputs=[name],
            name=f"make_{name}",
            value=helper.make_tensor("fill_value", TensorProto.FLOAT, [1], [0.0]),
        ))

    initializers = [shape_init]
    if external_initializer:
        ext = onnx.TensorProto()
        ext.CopyFrom(shape_init)
        ext.name = "external_init"
        ext.data_location = TensorProto.EXTERNAL
        entry = ext.external_data.add()
        entry.key = "location"
        entry.value = "nonexistent.bin"
        initializers.append(ext)

    graph = helper.make_graph(
        nodes, "test_graph", [input_vi], outputs, initializer=initializers
    )
    model = helper.make_model(graph, producer_name="test")
    del model.opset_import[:]
    model.opset_import.append(helper.make_opsetid("", opset_version))
    for domain, version in extra_opsets:
        model.opset_import.append(helper.make_opsetid(domain, version))
    model.ir_version = 8
    return model


@unittest.skipUnless(HAVE_ONNX, "onnx package not installed")
class ProjectPersonOutputTests(unittest.TestCase):
    def setUp(self):
        import onnx

        self.onnx = onnx
        self.model = _make_base_model(onnx)

    def test_does_not_mutate_original_model(self):
        before = self.model.SerializeToString()
        fpp.project_person_output(self.onnx, self.model)
        after = self.model.SerializeToString()
        self.assertEqual(before, after)

    def test_projected_output_shape_and_name(self):
        copy = fpp.project_person_output(self.onnx, self.model)
        self.assertEqual(len(copy.graph.output), 1)
        out = copy.graph.output[0]
        dims = tuple(d.dim_value for d in out.type.tensor_type.shape.dim)
        self.assertEqual(dims, (1, 8400, 6))
        self.assertEqual(out.type.tensor_type.elem_type, self.onnx.TensorProto.FLOAT)

    def test_slice_node_and_initializers_appended(self):
        copy = fpp.project_person_output(self.onnx, self.model)
        slice_nodes = [n for n in copy.graph.node if n.op_type == "Slice"]
        self.assertEqual(len(slice_nodes), 1)
        slice_node = slice_nodes[0]
        self.assertEqual(slice_node.input[0], "output")
        init_by_name = {i.name: i for i in copy.graph.initializer}
        start_name, end_name, axis_name, step_name = slice_node.input[1:5]
        for name, expected in (
            (start_name, [0]),
            (end_name, [6]),
            (axis_name, [2]),
            (step_name, [1]),
        ):
            init = init_by_name[name]
            self.assertEqual(init.data_type, self.onnx.TensorProto.INT64)
            self.assertEqual(list(self.onnx.numpy_helper.to_array(init)), expected)
        self.assertEqual(copy.graph.output[0].name, slice_node.output[0])

    def test_checker_passes_on_result(self):
        copy = fpp.project_person_output(self.onnx, self.model)
        self.onnx.checker.check_model(copy)

    def test_original_nodes_untouched(self):
        copy = fpp.project_person_output(self.onnx, self.model)
        original_node_names = {n.name for n in self.model.graph.node}
        copy_node_names = {n.name for n in copy.graph.node}
        self.assertTrue(original_node_names.issubset(copy_node_names))
        for name in original_node_names:
            orig = next(n for n in self.model.graph.node if n.name == name)
            dup = next(n for n in copy.graph.node if n.name == name)
            self.assertEqual(orig.SerializeToString(), dup.SerializeToString())

    def test_name_collision_avoided_when_prefix_already_used(self):
        onnx = self.onnx
        model = _make_base_model(onnx)
        # Pre-populate a node with the default prefix's generated names.
        colliding = onnx.helper.make_node(
            "Identity", inputs=["output"], outputs=["ft_perf_proj_slice_output"],
            name="ft_perf_proj_slice_node",
        )
        model.graph.node.append(colliding)
        # colliding introduces an extra dangling output; make it a real second output
        # is unnecessary here since we only check prefix collision avoidance logic.
        copy = fpp.project_person_output(onnx, model)
        slice_nodes = [n for n in copy.graph.node if n.op_type == "Slice"]
        self.assertEqual(len(slice_nodes), 1)
        self.assertNotEqual(slice_nodes[0].name, "ft_perf_proj_slice_node")
        self.assertNotEqual(slice_nodes[0].output[0], "ft_perf_proj_slice_output")
        onnx.checker.check_model(copy)

    def test_rejects_wrong_input_dtype(self):
        onnx = self.onnx
        model = helper_model = _make_base_model(onnx)
        model.graph.input[0].type.tensor_type.elem_type = onnx.TensorProto.INT64
        with self.assertRaises(fpp.ProjectionValidationError):
            fpp.project_person_output(onnx, model)

    def test_rejects_wrong_output_dtype(self):
        onnx = self.onnx
        model = _make_base_model(onnx)
        model.graph.output[0].type.tensor_type.elem_type = onnx.TensorProto.INT64
        with self.assertRaises(fpp.ProjectionValidationError):
            fpp.project_person_output(onnx, model)

    def test_rejects_non_static_input_shape(self):
        onnx = self.onnx
        model = _make_base_model(onnx)
        model.graph.input[0].type.tensor_type.shape.dim[0].dim_param = "N"
        with self.assertRaises(fpp.ProjectionValidationError):
            fpp.project_person_output(onnx, model)

    def test_rejects_non_static_output_shape(self):
        onnx = self.onnx
        model = _make_base_model(onnx)
        model.graph.output[0].type.tensor_type.shape.dim[1].dim_param = "N"
        with self.assertRaises(fpp.ProjectionValidationError):
            fpp.project_person_output(onnx, model)

    def test_rejects_wrong_output_shape(self):
        onnx = self.onnx
        model = _make_base_model(onnx, output_shape=(1, 8400, 84))
        with self.assertRaises(fpp.ProjectionValidationError):
            fpp.project_person_output(onnx, model)

    def test_rejects_wrong_batch_size(self):
        onnx = self.onnx
        model = _make_base_model(onnx, input_shape=(2, 3, 640, 640))
        with self.assertRaises(fpp.ProjectionValidationError):
            fpp.project_person_output(onnx, model)

    def test_rejects_multiple_outputs(self):
        onnx = self.onnx
        model = _make_base_model(onnx, num_outputs=2)
        with self.assertRaises(fpp.ProjectionValidationError):
            fpp.project_person_output(onnx, model)

    def test_rejects_old_opset(self):
        onnx = self.onnx
        model = _make_base_model(onnx, opset_version=9)
        with self.assertRaises(fpp.ProjectionValidationError):
            fpp.project_person_output(onnx, model)

    def test_rejects_missing_standard_opset(self):
        onnx = self.onnx
        model = _make_base_model(onnx)
        del model.opset_import[:]
        model.opset_import.append(onnx.helper.make_opsetid("custom.domain", 1))
        with self.assertRaises(fpp.ProjectionValidationError):
            fpp.project_person_output(onnx, model)

    def test_rejects_conflicting_standard_opset_versions(self):
        onnx = self.onnx
        model = _make_base_model(onnx, opset_version=11, extra_opsets=[("ai.onnx", 12)])
        with self.assertRaises(fpp.ProjectionValidationError):
            fpp.project_person_output(onnx, model)

    def test_rejects_external_initializer_data(self):
        onnx = self.onnx
        model = _make_base_model(onnx, external_initializer=True)
        with self.assertRaises(fpp.ProjectionValidationError):
            fpp.project_person_output(onnx, model)

    def test_accepts_explicit_ai_onnx_domain_matching_version(self):
        onnx = self.onnx
        model = _make_base_model(onnx, opset_version=11, extra_opsets=[("ai.onnx", 11)])
        copy = fpp.project_person_output(onnx, model)
        onnx.checker.check_model(copy)


def _make_three_head_model(onnx, opset_version=11, reshape_shape_value=(1, 85, -1),
                            share_shape_init=False, dynamic_shape_init=False,
                            num_reshapes=3):
    """Build a synthetic three-scale detection head graph.

    images -> [Shape/Gather/Concat -> ConstantOfShape -> Reshape] * N
            -> Concat(axis=2) -> Transpose([0, 2, 1]) -> output

    Each scale's ``ConstantOfShape`` shape is computed from the graph
    input's batch dim via Shape/Gather/Concat (not a static literal),
    so shape inference with ``data_prop=True`` can recompute it after
    the input batch dim is changed. Each Reshape's own shape input is
    a distinct, unshared INT64[3] initializer (the one under test).
    """
    helper = onnx.helper
    TensorProto = onnx.TensorProto

    input_vi = helper.make_tensor_value_info("images", TensorProto.FLOAT, [1, 3, 640, 640])

    nodes = []
    initializers = []
    value_info = []

    shape_of_images = helper.make_node("Shape", ["images"], ["shape_of_images"], name="shape_of_images")
    nodes.append(shape_of_images)
    value_info.append(helper.make_tensor_value_info("shape_of_images", TensorProto.INT64, [4]))

    batch_index_init = helper.make_tensor("batch_index", TensorProto.INT64, [1], [0])
    initializers.append(batch_index_init)
    gather_batch = helper.make_node(
        "Gather", ["shape_of_images", "batch_index"], ["batch"], name="gather_batch", axis=0
    )
    nodes.append(gather_batch)
    value_info.append(helper.make_tensor_value_info("batch", TensorProto.INT64, [1]))

    scales = [(80, 80), (40, 40), (20, 20)]
    reshaped_outputs = []
    for i, (h, w) in enumerate(scales[:num_reshapes]):
        scale_const_name = f"scale_const_{i}"
        initializers.append(
            helper.make_tensor(scale_const_name, TensorProto.INT64, [3], [85, h, w])
        )
        full_shape_name = f"full_shape_{i}"
        nodes.append(helper.make_node(
            "Concat", ["batch", scale_const_name], [full_shape_name],
            name=f"concat_shape_{i}", axis=0,
        ))
        value_info.append(helper.make_tensor_value_info(full_shape_name, TensorProto.INT64, [4]))

        feat_name = f"feat_{i}"
        nodes.append(helper.make_node(
            "ConstantOfShape", [full_shape_name], [feat_name], name=f"make_feat_{i}",
            value=helper.make_tensor("fill_value", TensorProto.FLOAT, [1], [0.0]),
        ))
        value_info.append(helper.make_tensor_value_info(feat_name, TensorProto.FLOAT, [1, 85, h, w]))

        if share_shape_init and i > 0:
            reshape_shape_name = f"reshape_shape_0"
        elif dynamic_shape_init and i == 0:
            reshape_shape_name = full_shape_name  # not an initializer
        else:
            reshape_shape_name = f"reshape_shape_{i}"
            initializers.append(
                helper.make_tensor(
                    reshape_shape_name, TensorProto.INT64, [len(reshape_shape_value)],
                    list(reshape_shape_value),
                )
            )

        reshaped_name = f"reshaped_{i}"
        nodes.append(helper.make_node(
            "Reshape", [feat_name, reshape_shape_name], [reshaped_name], name=f"reshape_{i}",
        ))
        value_info.append(helper.make_tensor_value_info(reshaped_name, TensorProto.FLOAT, [1, 85, h * w]))
        reshaped_outputs.append(reshaped_name)

    concat_out = "concat_heads"
    nodes.append(helper.make_node(
        "Concat", reshaped_outputs, [concat_out], name="concat_heads", axis=2,
    ))
    value_info.append(helper.make_tensor_value_info(concat_out, TensorProto.FLOAT, [1, 85, 8400]))

    output_name = "output"
    nodes.append(helper.make_node(
        "Transpose", [concat_out], [output_name], name="transpose_output", perm=[0, 2, 1],
    ))
    output_vi = helper.make_tensor_value_info(output_name, TensorProto.FLOAT, [1, 8400, 85])

    graph = helper.make_graph(
        nodes, "three_head_graph", [input_vi], [output_vi],
        initializer=initializers, value_info=value_info,
    )
    model = helper.make_model(graph, producer_name="test")
    del model.opset_import[:]
    model.opset_import.append(helper.make_opsetid("", opset_version))
    model.ir_version = 8
    onnx.checker.check_model(model)
    return model


@unittest.skipUnless(HAVE_ONNX, "onnx package not installed")
class MakeTwoCropBatchTests(unittest.TestCase):
    def setUp(self):
        import onnx

        self.onnx = onnx
        self.model = _make_three_head_model(onnx)

    def test_does_not_mutate_original_model(self):
        before = self.model.SerializeToString()
        fpp.make_two_crop_batch(self.onnx, self.model)
        after = self.model.SerializeToString()
        self.assertEqual(before, after)

    def test_rejects_nonbool_person_output(self):
        for bad in (1, 0, "true", None, 1.0):
            with self.assertRaises(fpp.ProjectionValidationError):
                fpp.make_two_crop_batch(self.onnx, self.model, person_output=bad)

    def test_batch_input_and_output_shape(self):
        result = fpp.make_two_crop_batch(self.onnx, self.model)
        in_dims = tuple(d.dim_value for d in result.graph.input[0].type.tensor_type.shape.dim)
        out_dims = tuple(d.dim_value for d in result.graph.output[0].type.tensor_type.shape.dim)
        self.assertEqual(in_dims, (2, 3, 640, 640))
        self.assertEqual(out_dims, (2, 8400, 85))

    def test_person_output_batch_shape(self):
        result = fpp.make_two_crop_batch(self.onnx, self.model, person_output=True)
        out_dims = tuple(d.dim_value for d in result.graph.output[0].type.tensor_type.shape.dim)
        self.assertEqual(out_dims, (2, 8400, 6))

    def test_three_reshape_shape_initializers_rewritten(self):
        result = fpp.make_two_crop_batch(self.onnx, self.model)
        reshape_nodes = [n for n in result.graph.node if n.op_type == "Reshape"]
        self.assertEqual(len(reshape_nodes), 3)
        init_by_name = {t.name: t for t in result.graph.initializer}
        seen_names = set()
        for node in reshape_nodes:
            shape_name = node.input[1]
            self.assertNotIn(shape_name, seen_names)
            seen_names.add(shape_name)
            values = list(self.onnx.numpy_helper.to_array(init_by_name[shape_name]))
            self.assertEqual(values, [0, 85, -1])

    def test_non_reshape_nodes_untouched(self):
        result = fpp.make_two_crop_batch(self.onnx, self.model)
        original_by_name = {n.name: n for n in self.model.graph.node if n.op_type != "Reshape"}
        result_by_name = {n.name: n for n in result.graph.node if n.op_type != "Reshape"}
        for name, orig in original_by_name.items():
            self.assertEqual(orig.SerializeToString(), result_by_name[name].SerializeToString())

    def test_stale_value_info_not_left_over(self):
        result = fpp.make_two_crop_batch(self.onnx, self.model)
        batched_prefixes = ("feat_", "reshaped_", "concat_heads")
        checked_any = False
        for value_info in result.graph.value_info:
            if not value_info.name.startswith(batched_prefixes):
                continue
            dims = value_info.type.tensor_type.shape.dim
            self.assertTrue(dims)
            # Shape inference may retain a symbolic batch through Shape/Gather.
            # Unknown is acceptable; a stale concrete batch=1 is not.
            if dims[0].WhichOneof("value") == "dim_value":
                self.assertEqual(dims[0].dim_value, 2)
            checked_any = True
        self.assertTrue(checked_any)

    def test_rejects_allowzero_that_would_create_empty_batch(self):
        model = _make_three_head_model(self.onnx)
        node = next(n for n in model.graph.node if n.op_type == "Reshape")
        node.attribute.append(self.onnx.helper.make_attribute("allowzero", 1))
        with self.assertRaises(fpp.ProjectionValidationError):
            fpp.make_two_crop_batch(self.onnx, model)

    @unittest.skipUnless(importlib.util.find_spec("onnxruntime"), "onnxruntime required")
    def test_runtime_infers_two_items_after_rebatching(self):
        import onnxruntime as ort
        import numpy as np
        model = fpp.make_two_crop_batch(self.onnx, self.model)
        model.ir_version = min(model.ir_version, 10)
        options = ort.SessionOptions()
        options.intra_op_num_threads = 1
        options.inter_op_num_threads = 1
        options.log_severity_level = 4
        session = ort.InferenceSession(model.SerializeToString(), sess_options=options,
                                       providers=["CPUExecutionProvider"])
        result = session.run(None, {session.get_inputs()[0].name:
                                   np.zeros((2, 3, 640, 640), dtype=np.float32)})[0]
        self.assertEqual(result.shape, (2, 8400, 85))

    def test_checker_passes_on_result(self):
        result = fpp.make_two_crop_batch(self.onnx, self.model)
        self.onnx.checker.check_model(result)

    def test_rejects_wrong_reshape_count(self):
        model = _make_three_head_model(self.onnx, num_reshapes=2)
        # Trim the dangling Concat input mismatch by rebuilding with 2 scales only
        # already handled inside _make_three_head_model via num_reshapes slicing.
        with self.assertRaises(fpp.ProjectionValidationError):
            fpp.make_two_crop_batch(self.onnx, model)

    def test_rejects_shared_shape_initializer(self):
        model = _make_three_head_model(self.onnx, share_shape_init=True)
        with self.assertRaises(fpp.ProjectionValidationError):
            fpp.make_two_crop_batch(self.onnx, model)

    def test_rejects_dynamic_shape_initializer(self):
        model = _make_three_head_model(self.onnx, dynamic_shape_init=True)
        with self.assertRaises(fpp.ProjectionValidationError):
            fpp.make_two_crop_batch(self.onnx, model)

    def test_rejects_wrong_shape_value(self):
        model = _make_three_head_model(self.onnx, reshape_shape_value=(1, 84, -1))
        with self.assertRaises(fpp.ProjectionValidationError):
            fpp.make_two_crop_batch(self.onnx, model)

    def test_rejects_old_opset(self):
        model = _make_three_head_model(self.onnx, opset_version=9)
        with self.assertRaises(fpp.ProjectionValidationError):
            fpp.make_two_crop_batch(self.onnx, model)


if __name__ == "__main__":
    unittest.main()
