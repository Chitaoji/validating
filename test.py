import unittest
from dataclasses import dataclass
from typing import Any, Literal

from src.validating import (
    ValidatorError,
    attr,
    validate,
)
from src.validating import (
    dataclass as validating_dataclass,
)


class TestAttrWithDataclasses(unittest.TestCase):
    def test_validating_dataclass_can_validate_public_methods(self):
        @validating_dataclass(validate_methods=True)
        class Config:
            retries: int = 3

            def add(self, x: int, y: int) -> int:
                return x + y

            @staticmethod
            def parse(x: int) -> int:
                return x

            @classmethod
            def from_count(cls, x: int):
                return cls(retries=x)

            def _internal(self, x: str) -> str:
                return x

        cfg = Config()
        self.assertEqual(cfg.add(1, 2), 3)
        self.assertEqual(cfg.parse(1), 1)
        self.assertEqual(cfg.from_count(4).retries, 4)
        self.assertEqual(cfg._internal(1), 1)

        with self.assertRaises(TypeError):
            cfg.add("1", 2)

        with self.assertRaises(TypeError):
            cfg.parse("1")

        with self.assertRaises(TypeError):
            cfg.from_count("4")

    def test_validating_dataclass_promotes_plain_defaults(self):
        @validating_dataclass
        class Config:
            retries: int = 3

        cfg = Config()
        self.assertEqual(cfg.retries, 3)
        with self.assertRaises(TypeError):
            cfg.retries = "bad"

    def test_validating_dataclass_promotes_required_fields(self):
        @validating_dataclass
        class Config:
            retries: int

        with self.assertRaises(TypeError):
            Config(retries="bad")

        cfg = Config(retries=3)
        with self.assertRaises(TypeError):
            cfg.retries = "bad"

    def test_validating_dataclass_supports_call_syntax(self):
        @validating_dataclass(eq=False)
        class Config:
            value: int = 1

        self.assertNotEqual(Config(), Config())

    def test_validating_dataclass_does_not_double_wrap_validated_methods(self):
        @validating_dataclass(validate_methods=True)
        class Config:
            @validate
            def method(self, x: int) -> int:
                return x

            @staticmethod
            @validate
            def parse(x: int) -> int:
                return x

            @classmethod
            @validate
            def from_count(cls, x: int):
                return cls()

        self.assertEqual(Config.method.__wrapped__.__name__, "method")
        self.assertEqual(Config.parse.__wrapped__.__name__, "parse")
        self.assertEqual(Config.from_count.__func__.__wrapped__.__name__, "from_count")
        self.assertFalse(hasattr(Config.method.__wrapped__, "__wrapped__"))
        self.assertFalse(hasattr(Config.parse.__wrapped__, "__wrapped__"))
        self.assertFalse(hasattr(Config.from_count.__func__.__wrapped__, "__wrapped__"))

    def test_default_value_is_lazily_applied(self):
        @dataclass
        class Config:
            retries: int = attr(default=3)

        cfg = Config()
        self.assertEqual(cfg.retries, 3)

    def test_missing_value_without_default_raises(self):
        @dataclass
        class Config:
            retries: int = attr()

        with self.assertRaisesRegex(
            TypeError,
            r"Config.__init__\(\) missing 1 required argument: 'retries'",
        ):
            Config()

    def test_type_validation_for_builtin_and_assignment(self):
        @dataclass
        class User:
            age: int = attr()

        with self.assertRaises(TypeError):
            User(age="20")

        u = User(age=20)
        with self.assertRaises(TypeError):
            u.age = "bad"

    def test_allowlist_and_denylist(self):
        @dataclass
        class Role:
            name: str = attr(allowlist=["admin", "guest"], denylist=["guest"])

        with self.assertRaises(ValueError):
            Role(name="user")

        with self.assertRaises(ValueError):
            Role(name="guest")

        obj = Role(name="admin")
        self.assertEqual(obj.name, "admin")

    def test_bounds_validation(self):
        @dataclass
        class RangeCfg:
            score: int = attr(lb=0, ub=100)

        with self.assertRaises(ValueError):
            RangeCfg(score=-1)

        with self.assertRaises(ValueError):
            RangeCfg(score=101)

        self.assertEqual(RangeCfg(score=60).score, 60)

    def test_bounds_validation_error_contains_combined_expectation(self):
        @dataclass
        class RangeCfg:
            score: int = attr(lb=1, ub=2)

        with self.assertRaisesRegex(ValueError, r"expected 1 ≤ score ≤ 2"):
            RangeCfg(score=0)

    def test_strict_bounds_validation(self):
        @dataclass
        class RangeCfg:
            score: int = attr(slb=0, sub=100)

        with self.assertRaises(ValueError):
            RangeCfg(score=0)

        with self.assertRaises(ValueError):
            RangeCfg(score=100)

        self.assertEqual(RangeCfg(score=60).score, 60)

    def test_strict_bounds_error_contains_combined_expectation(self):
        @dataclass
        class RangeCfg:
            score: int = attr(slb=1, ub=2)

        with self.assertRaisesRegex(ValueError, r"expected 1 < score ≤ 2"):
            RangeCfg(score=1)

    def test_custom_validator(self):
        @dataclass
        class EvenCfg:
            value: int = attr(validator=lambda x: x % 2 == 0)

        self.assertEqual(EvenCfg(value=10).value, 10)
        with self.assertRaises(ValueError):
            EvenCfg(value=11)

    def test_constructor_parameter_validation(self):
        with self.assertRaises(ValidatorError):
            attr(allowlist=(1, 2, 3))

        with self.assertRaises(ValidatorError):
            attr(denylist=(1, 2, 3))

        with self.assertRaises(ValidatorError):
            attr(lb=10, ub=1)

        with self.assertRaises(ValidatorError):
            attr(lb=1, slb=0)

        with self.assertRaises(ValidatorError):
            attr(ub=1, sub=2)

        with self.assertRaises(ValidatorError):
            attr(lb=1, sub=1)

        with self.assertRaises(ValidatorError):
            attr(slb=1, ub=1)

    def test_allowlist_element_type_check(self):
        with self.assertRaises(RuntimeError):

            @dataclass
            class BadAllowlist:
                value: int = attr(allowlist=[1, "2"])

    def test_denylist_element_type_is_not_checked_on_class_init(self):
        @dataclass
        class BadDenylist:
            value: int = attr(denylist=[1, "2"])

        obj = BadDenylist(value=2)
        self.assertEqual(obj.value, 2)

    def test_default_type_check_on_class_init(self):
        with self.assertRaises(RuntimeError):

            @dataclass
            class BadDefault:
                value: int = attr(default="1")

    def test_default_bound_check_on_class_init(self):
        with self.assertRaises(RuntimeError):

            @dataclass
            class BadDefaultBound:
                value: int = attr(default=0, lb=1)

    def test_default_allowlist_membership_check_on_class_init(self):
        with self.assertRaises(RuntimeError):

            @dataclass
            class BadDefaultAllowlist:
                value: int = attr(default=3, allowlist=[1, 2])

    def test_default_denylist_membership_check_on_class_init(self):
        with self.assertRaises(RuntimeError):

            @dataclass
            class BadDefaultDenylist:
                value: int = attr(default=2, denylist=[1, 2])

    def test_allowlist_bound_check_on_class_init(self):
        with self.assertRaises(RuntimeError):

            @dataclass
            class BadAllowlistBound:
                value: int = attr(allowlist=[1, 2], ub=1)

    def test_class_level_descriptor_access_and_any_type(self):
        @dataclass
        class GenericCfg:
            payload: Any = attr(default={"ok": True})

        self.assertIsNotNone(GenericCfg.payload)
        cfg = GenericCfg()
        cfg.payload = object()
        self.assertIsNotNone(cfg.payload)

    def test_string_annotation_is_resolved_for_attr(self):
        @dataclass
        class Config:
            retries: "int" = attr()

        self.assertEqual(Config(retries=1).retries, 1)
        with self.assertRaises(TypeError):
            Config(retries="1")

    def test_invalid_string_annotation_raises_for_attr(self):
        with self.assertRaisesRegex(RuntimeError, r"failed to resolve annotation"):

            @dataclass
            class Config:
                retries: "NotAType" = attr()

            class NotAType: ...

    def test_union_literal_and_collections(self):
        @dataclass
        class ComplexCfg:
            token: int | str = attr()
            mode: Literal["dev", "prod"] = attr()
            nums: list[int] = attr()
            point: tuple[int, int] = attr()
            tags: tuple[str, ...] = attr(default=("ok",))
            mapping: dict[str, int] = attr()
            uniq: set[int] = attr()

        cfg = ComplexCfg(
            token="a",
            mode="dev",
            nums=[1, 2],
            point=(3, 4),
            mapping={"x": 1},
            uniq={1, 2},
        )
        self.assertEqual(cfg.tags, ("ok",))

        with self.assertRaises(TypeError):
            cfg.mode = "qa"

        with self.assertRaises(TypeError):
            cfg.nums = [1, "2"]

        with self.assertRaises(TypeError):
            cfg.point = (1, 2, 3)

        with self.assertRaises(TypeError):
            cfg.mapping = {1: 2}

        with self.assertRaises(TypeError):
            cfg.uniq = {1, "2"}

    def test_delete_attribute(self):
        @dataclass
        class Config:
            retries: int = attr(default=3)

        cfg = Config()
        self.assertEqual(cfg.retries, 3)
        del cfg.retries
        self.assertEqual(cfg.retries, 3)

    def test_default_factory_produces_per_instance_value(self):
        @dataclass
        class Config:
            payload: list[int] = attr(default_factory=list)

        first = Config()
        second = Config()
        first.payload.append(1)
        self.assertEqual(first.payload, [1])
        self.assertEqual(second.payload, [])

    def test_default_and_default_factory_cannot_be_set_together(self):
        with self.assertRaises(ValidatorError):
            attr(default=1, default_factory=lambda: 1)

    def test_default_factory_type_check_on_class_init(self):
        with self.assertRaises(RuntimeError):

            @dataclass
            class BadDefaultFactory:
                value: int = attr(default_factory=lambda: "1")

    def test_default_custom_validator_check_on_class_init(self):
        with self.assertRaises(RuntimeError):

            @dataclass
            class BadDefaultValidator:
                value: int = attr(default=3, validator=lambda x: x % 2 == 0)

    def test_default_factory_custom_validator_check_on_class_init(self):
        with self.assertRaises(RuntimeError):

            @dataclass
            class BadDefaultFactoryValidator:
                value: int = attr(
                    default_factory=lambda: 3, validator=lambda x: x % 2 == 0
                )

    def test_init_false_excludes_parameter_and_keeps_default(self):
        @dataclass
        class Config:
            retries: int = attr(default=3, init=False)

        cfg = Config()
        self.assertEqual(cfg.retries, 3)

        with self.assertRaises(TypeError):
            Config(retries=10)

    def test_init_option_must_be_bool(self):
        with self.assertRaises(ValidatorError):
            attr(init=1)

    def test_repr_option_controls_dataclass_repr(self):
        @dataclass
        class Config:
            visible: int = attr(default=1)
            hidden: int = attr(default=2, repr=False)

        config_repr = repr(Config())
        self.assertIn("visible=1", config_repr)
        self.assertNotIn("hidden=2", config_repr)

    def test_compare_option_controls_equality(self):
        @dataclass
        class Config:
            stable: int = attr(default=1)
            volatile: int = attr(default=1, compare=False)

        self.assertEqual(Config(stable=1, volatile=1), Config(stable=1, volatile=2))

    def test_hash_option_controls_hashing(self):
        @dataclass(unsafe_hash=True)
        class Config:
            included: int = attr(default=1, hash=True)
            skipped: int = attr(default=1, hash=False)

        self.assertEqual(
            hash(Config(included=1, skipped=1)),
            hash(Config(included=1, skipped=2)),
        )

    def test_kw_only_option_requires_keyword_argument(self):
        @dataclass
        class Config:
            positional: int = attr()
            keyword_only: int = attr(kw_only=True)

        self.assertEqual(Config(1, keyword_only=2).keyword_only, 2)
        with self.assertRaises(TypeError):
            Config(1, 2)

    def test_repr_hash_compare_kw_only_options_must_be_bool_or_none(self):
        with self.assertRaises(ValidatorError):
            attr(repr=1)

        with self.assertRaises(ValidatorError):
            attr(hash="bad")

        with self.assertRaises(ValidatorError):
            attr(compare=1)

        with self.assertRaises(ValidatorError):
            attr(kw_only=1)

    def test_slots_true_is_not_supported(self):
        @dataclass(slots=True)
        class Config:
            retries: int = attr(default=1)

        with self.assertRaisesRegex(
            RuntimeError, r"dataclasses with slots=True are not supported"
        ):
            Config()


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

    def test_validate_resolves_string_annotations(self):
        @validate
        def add(a: "int", b: "int") -> int:
            return a + b

        self.assertEqual(add(1, 2), 3)
        with self.assertRaises(TypeError):
            add("1", 2)

    def test_validate_raises_for_unresolvable_string_annotation(self):
        with self.assertRaisesRegex(TypeError, r"failed to resolve annotation"):

            @validate
            def add(a: "NotAType") -> int:
                return a

            class NotAType: ...

    def test_validate_works_with_complex_type_hints(self):
        @validate
        def configure(mode: Literal["dev", "prod"], opts: dict[str, int]):
            return mode, opts

        self.assertEqual(configure("dev", {"a": 1}), ("dev", {"a": 1}))
        with self.assertRaises(TypeError):
            configure("test", {"a": 1})
        with self.assertRaises(TypeError):
            configure("dev", {"a": "1"})

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


if __name__ == "__main__":
    unittest.main()
