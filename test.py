import unittest
from dataclasses import dataclass
from typing import Any, Literal

from src.validating import ValidatorError, attr


class TestAttrWithDataclasses(unittest.TestCase):
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

    def test_strict_bounds_validation(self):
        @dataclass
        class RangeCfg:
            score: int = attr(slb=0, sub=100)

        with self.assertRaises(ValueError):
            RangeCfg(score=0)

        with self.assertRaises(ValueError):
            RangeCfg(score=100)

        self.assertEqual(RangeCfg(score=60).score, 60)

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


if __name__ == "__main__":
    unittest.main()
