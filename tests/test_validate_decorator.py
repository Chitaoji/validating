import unittest
import sys
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import ForwardRef, Literal, TypedDict

try:
    from typing import Unpack
except ImportError:
    from typing_extensions import Unpack

from src.validating import validate


class TestValidateFunctionDecorator(unittest.TestCase):
    def test_validate_checks_positional_and_keyword_arguments(self):
        @validate
        def add(a: int, b: int) -> int:
            return a + b

        self.assertEqual(add(1, b=2), 3)
        with self.assertRaises(TypeError):
            add("1", b=2)

    def test_validate_ignores_unannotated_arguments(self):
        @validate
        def normalize(a, b: int):
            return a, b

        self.assertEqual(normalize("x", 1), ("x", 1))

    def test_validate_checks_varargs_and_kwargs(self):
        @validate
        def collect(*args: int, **kwargs: str):
            return args, kwargs

        self.assertEqual(collect(1, 2, key="v"), ((1, 2), {"key": "v"}))
        with self.assertRaises(TypeError):
            collect(1, "2", key="v")
        with self.assertRaises(TypeError):
            collect(1, 2, key=3)

    def test_validate_supports_unpack_typed_dict_for_kwargs(self):
        class Query(TypedDict):
            limit: int
            cursor: str

        @validate
        def fetch(**kwargs: Unpack[Query]):
            return kwargs

        self.assertEqual(fetch(limit=1, cursor="next"), {"limit": 1, "cursor": "next"})
        with self.assertRaises(TypeError):
            fetch(limit="1", cursor="next")
        with self.assertRaises(TypeError):
            fetch(limit=1)
        with self.assertRaises(TypeError):
            fetch(limit=1, cursor="next", extra="x")

    def test_validate_resolves_string_annotations(self):
        @validate
        def add(a: "int", b: "int") -> int:
            return a + b

        self.assertEqual(add(1, 2), 3)
        with self.assertRaises(TypeError):
            add("1", 2)

    def test_validate_accepts_union_with_unresolved_forward_ref(self):
        @validate
        def set_figure(kwargs: ForwardRef("SubplotDict") | None):
            return kwargs

        self.assertEqual(
            set_figure({"left": 0.1, "right": 0.9}),
            {"left": 0.1, "right": 0.9},
        )
        self.assertIsNone(set_figure(None))

    def test_validate_resolves_forward_string_annotations_in_local_scope(self):
        @validate
        def build(value: "LaterType") -> "LaterType":
            return value

        class LaterType: ...

        instance = LaterType()
        self.assertIs(build(instance), instance)
        with self.assertRaises(TypeError):
            build(1)

    def test_validate_type_checking_import_is_lazily_loaded(self):
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "lazy_v_models.py").write_text(
                "class LaterType:\n"
                "    pass\n",
                encoding="utf-8",
            )
            (root / "lazy_v_consumer.py").write_text(
                "from typing import TYPE_CHECKING\n"
                "from src.validating import validate\n"
                "\n"
                "if TYPE_CHECKING:\n"
                "    from lazy_v_models import LaterType\n"
                "\n"
                "@validate\n"
                "def build(value: 'LaterType') -> 'LaterType':\n"
                "    return value\n",
                encoding="utf-8",
            )

            self.assertNotIn("lazy_v_models", sys.modules)

            consumer_spec = spec_from_file_location("lazy_v_consumer", root / "lazy_v_consumer.py")
            assert consumer_spec is not None and consumer_spec.loader is not None
            consumer_module = module_from_spec(consumer_spec)
            sys.modules["lazy_v_consumer"] = consumer_module
            consumer_spec.loader.exec_module(consumer_module)

            self.assertNotIn("lazy_v_models", sys.modules)

            models_spec = spec_from_file_location("lazy_v_models", root / "lazy_v_models.py")
            assert models_spec is not None and models_spec.loader is not None
            models_module = module_from_spec(models_spec)
            sys.modules["lazy_v_models"] = models_module
            models_spec.loader.exec_module(models_module)

            instance = models_module.LaterType()
            self.assertIs(consumer_module.build(instance), instance)
            with self.assertRaises(TypeError):
                consumer_module.build(1)

    def test_validate_resolves_forward_annotation_from_type_checking_import(self):
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "models.py").write_text(
                "class LaterType:\n"
                "    pass\n",
                encoding="utf-8",
            )
            (root / "consumer.py").write_text(
                "from typing import TYPE_CHECKING\n"
                "from src.validating import validate\n"
                "\n"
                "if TYPE_CHECKING:\n"
                "    from models import LaterType\n"
                "\n"
                "@validate\n"
                "def build(value: 'LaterType') -> 'LaterType':\n"
                "    return value\n",
                encoding="utf-8",
            )

            models_spec = spec_from_file_location("models", root / "models.py")
            assert models_spec is not None and models_spec.loader is not None
            models_module = module_from_spec(models_spec)
            sys.modules["models"] = models_module
            models_spec.loader.exec_module(models_module)

            consumer_spec = spec_from_file_location("consumer", root / "consumer.py")
            assert consumer_spec is not None and consumer_spec.loader is not None
            consumer_module = module_from_spec(consumer_spec)
            sys.modules["consumer"] = consumer_module
            consumer_spec.loader.exec_module(consumer_module)

            instance = models_module.LaterType()
            self.assertIs(consumer_module.build(instance), instance)
            with self.assertRaises(TypeError):
                consumer_module.build(1)

    def test_validate_raises_for_unresolvable_string_annotation(self):
        @validate
        def add(a: "MissingType") -> int:
            return a

        with self.assertRaisesRegex(TypeError, r"failed to resolve annotation"):
            add(1)

        class MissingType: ...

    def test_validate_works_with_complex_type_hints(self):
        @validate
        def configure(mode: Literal["dev", "prod"], opts: dict[str, int]):
            return mode, opts

        self.assertEqual(configure("dev", {"a": 1}), ("dev", {"a": 1}))
        with self.assertRaises(TypeError):
            configure("test", {"a": 1})
        with self.assertRaises(TypeError):
            configure("dev", {"a": "1"})

    def test_validate_literal_union_with_numpy_array(self):
        try:
            import numpy as np
        except ImportError:
            self.skipTest("numpy is not installed")

        @validate
        def func(a: Literal[1, 2] | np.ndarray):
            return a

        arr = np.array([1, 2, 3])
        self.assertTrue((func(arr) == arr).all())

    def test_validate_literal_union_handles_ambiguous_equality_result(self):
        class AmbiguousBool:
            def __bool__(self):
                raise ValueError("ambiguous truth value")

        class WeirdValue:
            def __eq__(self, _other):
                return AmbiguousBool()

        @validate
        def func(a: Literal[1, 2] | WeirdValue):
            return a

        value = WeirdValue()
        self.assertIs(func(value), value)

    def test_validate_preserves_assertion_error_with_message(self):
        @validate
        def check(a: int) -> int:
            assert a > 1, "a>1"
            return a

        self.assertEqual(check(2), 2)
        with self.assertRaisesRegex(AssertionError, r"a>1"):
            check(1)

    def test_validate_converts_assertion_without_message_to_value_error(self):
        @validate
        def check(a: int) -> int:
            assert a > 1
            return a

        self.assertEqual(check(2), 2)

        import traceback

        try:
            check(1)
        except ValueError as exc:
            self.assertEqual(
                str(exc),
                "invalid value for argument 'a' of check: "
                "expected a > 1, got 1 instead",
            )
            tb_text = "".join(traceback.format_tb(exc.__traceback__))
            self.assertRegex(tb_text, r"assert a > 1")
        else:
            self.fail("ValueError was not raised")

    def test_validate_conversion_hides_assertion_error_context(self):
        @validate
        def check(a: int) -> int:
            assert a > 1
            return a

        with self.assertRaises(ValueError) as context:
            check(1)

        self.assertIsNone(context.exception.__cause__)
        self.assertTrue(context.exception.__suppress_context__)

    def test_validate_converts_parenthesized_assertion_to_value_error(self):
        @validate
        def check(a: int) -> int:
            assert a > 1
            return a

        self.assertEqual(check(2), 2)
        with self.assertRaisesRegex(
            ValueError,
            "invalid value for argument 'a' of check: expected (a > 1), got 1 instead",
        ):
            check(1)

    def test_validate_converts_chained_assertion_with_argument_in_middle(self):
        @validate
        def check(a: float) -> float:
            assert 1 < a < 2
            return a

        self.assertEqual(check(1.5), 1.5)
        with self.assertRaisesRegex(
            ValueError,
            "invalid value for argument 'a' of check: "
            "expected 1 < a < 2, got 3.0 instead",
        ):
            check(3.0)

    def test_validate_converts_chained_assertion_with_argument_on_right(self):
        @validate
        def check(a: int) -> int:
            assert 3 > a >= 2
            return a

        self.assertEqual(check(2), 2)
        with self.assertRaisesRegex(ValueError, r"expected 3 > a >= 2, got 1 instead"):
            check(1)

    def test_validate_converts_multiline_assertion_to_value_error(self):
        @validate
        def check(a: float) -> float:
            assert 1 < a < 2
            return a

        self.assertEqual(check(1.5), 1.5)
        with self.assertRaisesRegex(
            ValueError, r"expected 1 < a < 2, got 3\.0 instead"
        ):
            check(3.0)

    def test_validate_converts_parenthesized_split_line_assertion_to_value_error(self):
        @validate
        def check(a: int) -> int:
            assert a >= 10
            return a

        self.assertEqual(check(10), 10)
        with self.assertRaisesRegex(ValueError, r"expected a >= 10, got 9 instead"):
            check(9)

    def test_validate_converts_backslash_split_line_assertion_to_value_error(self):
        @validate
        def check(a: int) -> int:
            assert a >= 10
            return a

        self.assertEqual(check(10), 10)
        with self.assertRaisesRegex(ValueError, r"expected a >= 10, got 9 instead"):
            check(9)

    def test_validate_preserves_assertion_for_non_argument_expression(self):
        @validate
        def check(a: int) -> int:
            local = a + 1
            assert local > 2
            return a

        self.assertEqual(check(2), 2)
        with self.assertRaises(AssertionError):
            check(1)
