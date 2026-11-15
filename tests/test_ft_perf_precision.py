"""Tests for the experimental ft_perf_precision FP16 ONNX graph helper.

Builds a tiny synthetic ONNX graph (declared shapes plus one small
scalar weight, no real inference) rather than loading any real model.
Skipped entirely under a plain stdlib interpreter without the optional
``onnx``/``numpy`` packages. No network access and no real inference.
"""
import importlib.util
import unittest

from tools import ft_perf_precision as fpp

HAVE_ONNX = importlib.util.find_spec("onnx") is not None
HAVE_NUMPY = importlib.util.find_spec("numpy") is not None
HAVE_ONNXRUNTIME = importlib.util.find_spec("onnxruntime") is not None


def _make_base_model(onnx, batch_size=1, columns=85, bias_value=0.5,
                      external_initializer=False, extra_node_domain=None,
                      num_outputs=1):
    """images -> ConstantOfShape(shape) -> Add(bias) -> output.

    ``bias`` is a small real FLOAT[1] initializer so a converter has a
    genuine weight to narrow to FLOAT16; no node here needs real
    numeric inference to validate shapes/types.
    """
    helper = onnx.helper
    TensorProto = onnx.TensorProto

    input_vi = helper.make_tensor_value_info(
        "images", TensorProto.FLOAT, [batch_size, 3, 640, 640]
    )

    out_shape = (batch_size, 8400, columns)
    shape_init = helper.make_tensor(
        "shape_init", TensorProto.INT64, [len(out_shape)], list(out_shape)
    )
    bias_init = helper.make_tensor("bias", TensorProto.FLOAT, [1], [bias_value])

    initializers = [shape_init, bias_init]
    if external_initializer:
        ext = onnx.TensorProto()
        ext.CopyFrom(bias_init)
        ext.name = "external_bias"
        ext.data_location = TensorProto.EXTERNAL
        entry = ext.external_data.add()
        entry.key = "location"
        entry.value = "nonexistent.bin"
        initializers.append(ext)

    nodes = [
        helper.make_node(
            "ConstantOfShape", ["shape_init"], ["raw_output"], name="make_raw_output",
            value=helper.make_tensor("fill_value", TensorProto.FLOAT, [1], [0.0]),
        ),
    ]
    add_node = helper.make_node("Add", ["raw_output", "bias"], ["output"], name="add_bias")
    if extra_node_domain is not None:
        add_node.domain = extra_node_domain
    nodes.append(add_node)

    outputs = [helper.make_tensor_value_info("output", TensorProto.FLOAT, list(out_shape))]
    for i in range(1, num_outputs):
        outputs.append(
            helper.make_tensor_value_info(f"output_{i}", TensorProto.FLOAT, list(out_shape))
        )

    graph = helper.make_graph(nodes, "test_graph", [input_vi], outputs, initializer=initializers)
    model = helper.make_model(graph, producer_name="test")
    del model.opset_import[:]
    model.opset_import.append(helper.make_opsetid("", 13))
    model.ir_version = 8
    return model


def _fp16_copy(onnx, model):
    """Minimal stand-in for ``convert_float_to_float16``: narrows ``bias``."""
    import numpy as np

    result = onnx.ModelProto()
    result.CopyFrom(model)
    for initializer in result.graph.initializer:
        if initializer.name == "bias":
            values = onnx.numpy_helper.to_array(initializer).astype(np.float16)
            narrowed = onnx.numpy_helper.from_array(values, initializer.name)
            initializer.CopyFrom(narrowed)
    result.graph.node.insert(0, onnx.helper.make_node(
        "Cast", ["bias"], ["bias_float"], to=onnx.TensorProto.FLOAT))
    for node in result.graph.node:
        if node.op_type == "Add":
            node.input[1] = "bias_float"
    return result


class SpyConverter:
    def __init__(self, result_factory):
        self.calls = []
        self.result_factory = result_factory

    def __call__(self, model, **kwargs):
        self.calls.append((model, dict(kwargs)))
        return self.result_factory(model)


@unittest.skipUnless(HAVE_ONNX and HAVE_NUMPY, "onnx and numpy packages required")
class MakeFp16ModelTests(unittest.TestCase):
    def setUp(self):
        import onnx

        self.onnx = onnx
        self.model = _make_base_model(onnx)

    def _valid_spy(self):
        onnx = self.onnx
        return SpyConverter(lambda model: _fp16_copy(onnx, model))

    def test_converter_called_once_with_exact_policy_kwargs(self):
        spy = self._valid_spy()
        fpp.make_fp16_model(self.onnx, self.model, spy)
        self.assertEqual(len(spy.calls), 1)
        _, kwargs = spy.calls[0]
        expected = {k: v for k, v in fpp.CONVERSION_POLICY.items() if k != "version"}
        self.assertEqual(kwargs, expected)

    def test_converter_receives_deepcopy_not_original(self):
        spy = self._valid_spy()
        before = self.model.SerializeToString()
        fpp.make_fp16_model(self.onnx, self.model, spy)
        passed_model, _ = spy.calls[0]
        self.assertIsNot(passed_model, self.model)
        self.assertEqual(passed_model.SerializeToString(), before)

    def test_does_not_mutate_original_model(self):
        spy = self._valid_spy()
        before = self.model.SerializeToString()
        fpp.make_fp16_model(self.onnx, self.model, spy)
        self.assertEqual(self.model.SerializeToString(), before)

    def test_result_is_separate_copy_from_converter_return_value(self):
        onnx = self.onnx
        converted_holder = {}

        def factory(model):
            converted = _fp16_copy(onnx, model)
            converted_holder["converted"] = converted
            return converted

        spy = SpyConverter(factory)
        result = fpp.make_fp16_model(onnx, self.model, spy)
        self.assertIsNot(result, converted_holder["converted"])
        before = converted_holder["converted"].SerializeToString()
        result.graph.node.add().name = "mutated_after_return"
        self.assertEqual(converted_holder["converted"].SerializeToString(), before)

    def test_valid_result_float32_io_and_internal_fp16(self):
        spy = self._valid_spy()
        result = fpp.make_fp16_model(self.onnx, self.model, spy)
        self.assertEqual(result.graph.input[0].type.tensor_type.elem_type, self.onnx.TensorProto.FLOAT)
        self.assertEqual(result.graph.output[0].type.tensor_type.elem_type, self.onnx.TensorProto.FLOAT)
        bias = next(t for t in result.graph.initializer if t.name == "bias")
        self.assertEqual(bias.data_type, self.onnx.TensorProto.FLOAT16)

    def test_rejects_converter_exception(self):
        def raising(model, **kwargs):
            raise RuntimeError("boom")

        with self.assertRaises(fpp.PrecisionValidationError):
            fpp.make_fp16_model(self.onnx, self.model, raising)

    def test_rejects_non_modelproto_converter_result(self):
        with self.assertRaises(fpp.PrecisionValidationError):
            fpp.make_fp16_model(self.onnx, self.model, lambda model, **kwargs: None)

    def test_unsupported_tensor_dtype_rejected_before_and_after_conversion(self):
        onnx = self.onnx
        for stage in ("before", "after"):
            with self.subTest(stage=stage):
                model = _make_base_model(onnx)

                def add_double(target):
                    target.graph.initializer.append(
                        onnx.helper.make_tensor("unsupported", onnx.TensorProto.DOUBLE, [1], [0.5]))
                    return target

                if stage == "before":
                    add_double(model)
                spy = SpyConverter(lambda value: add_double(_fp16_copy(onnx, value))
                                   if stage == "after" else _fp16_copy(onnx, value))
                with self.assertRaisesRegex(fpp.PrecisionValidationError, "unsupported tensor dtype"):
                    fpp.make_fp16_model(onnx, model, spy)
                self.assertEqual(len(spy.calls), 0 if stage == "before" else 1)

    def test_nonfinite_float_attributes_rejected_before_and_after_conversion(self):
        onnx = self.onnx
        for stage in ("before", "after"):
            for attr_name in ("value_float", "value_floats"):
                for bad in (float("nan"), float("inf"), -float("inf")):
                    with self.subTest(stage=stage, attr=attr_name, value=bad):
                        model = _make_base_model(onnx)

                        def add_nonfinite(target):
                            value = [bad] if attr_name == "value_floats" else bad
                            target.graph.node.append(onnx.helper.make_node(
                                "Constant", [], ["unsupported"], **{attr_name: value}))
                            return target

                        if stage == "before":
                            add_nonfinite(model)
                        spy = SpyConverter(lambda value: add_nonfinite(_fp16_copy(onnx, value))
                                           if stage == "after" else _fp16_copy(onnx, value))
                        with self.assertRaisesRegex(fpp.PrecisionValidationError, "non-finite float attribute"):
                            fpp.make_fp16_model(onnx, model, spy)
                        self.assertEqual(len(spy.calls), 0 if stage == "before" else 1)

    def test_rejects_output_shape_changed_by_converter(self):
        onnx = self.onnx

        def bad_factory(model):
            converted = _fp16_copy(onnx, model)
            del converted.graph.output[:]
            converted.graph.output.append(
                onnx.helper.make_tensor_value_info("output", onnx.TensorProto.FLOAT, [1, 8400, 6])
            )
            return converted

        with self.assertRaises(fpp.PrecisionValidationError):
            fpp.make_fp16_model(onnx, self.model, SpyConverter(bad_factory))

    def test_rejects_result_without_internal_fp16(self):
        onnx = self.onnx

        def no_fp16_factory(model):
            copy_model = onnx.ModelProto()
            copy_model.CopyFrom(model)
            return copy_model

        with self.assertRaises(fpp.PrecisionValidationError):
            fpp.make_fp16_model(onnx, self.model, SpyConverter(no_fp16_factory))

    def test_rejects_result_with_nonfinite_weight(self):
        onnx = self.onnx
        import numpy as np

        def nonfinite_factory(model):
            converted = _fp16_copy(onnx, model)
            for initializer in converted.graph.initializer:
                if initializer.name == "bias":
                    narrowed = onnx.numpy_helper.from_array(
                        np.array([np.float16("inf")]), initializer.name
                    )
                    initializer.CopyFrom(narrowed)
            return converted

        with self.assertRaises(fpp.PrecisionValidationError):
            fpp.make_fp16_model(onnx, self.model, SpyConverter(nonfinite_factory))

    def test_rejects_mixed_precision_add_without_required_cast(self):
        def bad_factory(model):
            result = _fp16_copy(self.onnx, model)
            for node in result.graph.node:
                if node.op_type == "Add":
                    node.input[1] = "bias"
            return result
        with self.assertRaises(fpp.PrecisionValidationError):
            fpp.make_fp16_model(self.onnx, self.model, SpyConverter(bad_factory))

    def test_converter_not_called_when_input_validation_fails(self):
        onnx = self.onnx
        model = _make_base_model(onnx, batch_size=3)
        spy = self._valid_spy()
        with self.assertRaises(fpp.PrecisionValidationError):
            fpp.make_fp16_model(onnx, model, spy)
        self.assertEqual(spy.calls, [])

    def test_rejects_unsupported_batch_size(self):
        onnx = self.onnx
        model = _make_base_model(onnx, batch_size=3)
        with self.assertRaises(fpp.PrecisionValidationError):
            fpp.make_fp16_model(onnx, model, self._valid_spy())

    def test_rejects_unsupported_output_columns(self):
        onnx = self.onnx
        model = _make_base_model(onnx, columns=10)
        with self.assertRaises(fpp.PrecisionValidationError):
            fpp.make_fp16_model(onnx, model, self._valid_spy())

    def test_rejects_multiple_outputs(self):
        onnx = self.onnx
        model = _make_base_model(onnx, num_outputs=2)
        with self.assertRaises(fpp.PrecisionValidationError):
            fpp.make_fp16_model(onnx, model, self._valid_spy())

    def test_rejects_external_initializer(self):
        onnx = self.onnx
        model = _make_base_model(onnx, external_initializer=True)
        with self.assertRaises(fpp.PrecisionValidationError):
            fpp.make_fp16_model(onnx, model, self._valid_spy())

    def test_rejects_custom_domain_node(self):
        onnx = self.onnx
        model = _make_base_model(onnx, extra_node_domain="custom.domain")
        with self.assertRaises(fpp.PrecisionValidationError):
            fpp.make_fp16_model(onnx, model, self._valid_spy())

    def test_rejects_nonfinite_initializer(self):
        onnx = self.onnx
        model = _make_base_model(onnx, bias_value=float("inf"))
        with self.assertRaises(fpp.PrecisionValidationError):
            fpp.make_fp16_model(onnx, model, self._valid_spy())

    def test_rejects_overflow_initializer(self):
        onnx = self.onnx
        model = _make_base_model(onnx, bias_value=1e5)
        with self.assertRaises(fpp.PrecisionValidationError):
            fpp.make_fp16_model(onnx, model, self._valid_spy())

    def test_rejects_subgraph_attribute(self):
        onnx = self.onnx
        model = _make_base_model(onnx)
        inner_graph = onnx.helper.make_graph([], "inner", [], [])
        bogus_node = onnx.helper.make_node(
            "If", ["bias"], ["bogus_output"], name="bogus_if",
            then_branch=inner_graph, else_branch=inner_graph,
        )
        model.graph.node.append(bogus_node)
        with self.assertRaises(fpp.PrecisionValidationError):
            fpp.make_fp16_model(onnx, model, self._valid_spy())

    def test_rejects_sparse_initializer(self):
        onnx = self.onnx
        model = _make_base_model(onnx)
        sparse = model.graph.sparse_initializer.add()
        sparse.values.data_type = onnx.TensorProto.FLOAT
        with self.assertRaises(fpp.PrecisionValidationError):
            fpp.make_fp16_model(onnx, model, self._valid_spy())

    def test_rejects_sparse_tensor_attribute_before_converter(self):
        model = _make_base_model(self.onnx)
        attr = model.graph.node[0].attribute.add()
        attr.name = "sparse_value"
        attr.type = self.onnx.AttributeProto.SPARSE_TENSOR
        spy = self._valid_spy()
        with self.assertRaises(fpp.PrecisionValidationError):
            fpp.make_fp16_model(self.onnx, model, spy)
        self.assertEqual(spy.calls, [])

    def test_conversion_policy_is_versioned_numeric_dict(self):
        self.assertIn("version", fpp.CONVERSION_POLICY)
        self.assertEqual(fpp.CONVERSION_POLICY["keep_io_types"], True)
        self.assertEqual(fpp.CONVERSION_POLICY["min_positive_val"], 5.96e-08)
        self.assertEqual(fpp.CONVERSION_POLICY["max_finite_val"], 65504.0)
        self.assertEqual(fpp.CONVERSION_POLICY["disable_shape_infer"], False)


@unittest.skipUnless(HAVE_ONNX and HAVE_NUMPY and HAVE_ONNXRUNTIME,
                      "onnx, numpy and onnxruntime packages required")
class MakeFp16ModelRealConverterTests(unittest.TestCase):
    """Optional end-to-end check against the actual onnxruntime converter."""

    def test_real_converter_clamp_rounding_and_unchanged_original(self):
        import onnx
        from onnxruntime.transformers.float16 import convert_float_to_float16

        model = _make_base_model(onnx, bias_value=1e-10)
        before = model.SerializeToString()

        result = fpp.make_fp16_model(onnx, model, convert_float_to_float16)

        self.assertEqual(model.SerializeToString(), before)
        onnx.checker.check_model(result)
        self.assertEqual(result.graph.input[0].type.tensor_type.elem_type, onnx.TensorProto.FLOAT)
        self.assertEqual(result.graph.output[0].type.tensor_type.elem_type, onnx.TensorProto.FLOAT)
        bias = next(t for t in result.graph.initializer if t.name == "bias")
        self.assertEqual(bias.data_type, onnx.TensorProto.FLOAT16)
        narrowed_value = float(onnx.numpy_helper.to_array(bias)[0])
        import numpy as np
        self.assertEqual(narrowed_value, float(np.float16(5.96e-08)))

    def test_appended_input_cast_is_sorted_and_output_name_preserved(self):
        import onnx
        from onnxruntime.transformers.float16 import convert_float_to_float16
        model = _make_base_model(onnx)
        model.graph.node.insert(0, onnx.helper.make_node("Identity", ["images"], ["image_copy"]))
        result = fpp.make_fp16_model(onnx, model, convert_float_to_float16)
        onnx.checker.check_model(result)
        self.assertEqual(result.graph.input[0].name, "images")
        self.assertEqual(result.graph.output[0].name, "output")

    def test_rejects_converter_cycle_and_changed_io_name(self):
        import onnx
        for mode in ("cycle", "name"):
            def bad(model, **kwargs):
                result = _fp16_copy(onnx, model)
                if mode == "cycle":
                    result.graph.node.extend([
                        onnx.helper.make_node("Identity", ["b"], ["a"]),
                        onnx.helper.make_node("Identity", ["a"], ["b"])])
                else:
                    result.graph.input[0].name = "changed"
                return result
            with self.assertRaises(fpp.PrecisionValidationError):
                fpp.make_fp16_model(onnx, _make_base_model(onnx), bad)


if __name__ == "__main__":
    unittest.main()
