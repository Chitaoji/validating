# validating

`validating` is a lightweight runtime validation library focused on making
`dataclass` fields and function arguments safer and easier to validate.

It exposes three main entry points:

- `attr(...)`: declare validated fields (type checks, bounds, allow/deny lists, custom validators)
- `@dataclass(...)`: a compatible enhancement of `dataclasses.dataclass` with automatic validation integration
- `@validate`: a decorator that validates function arguments using type annotations

## Installation

```bash
pip install validating
```

## Quick Start

```python
from validating import attr, dataclass

@dataclass
class UserConfig:
    age: int = attr(lb=0)
    role: str = attr(allowlist=["admin", "user"])

cfg = UserConfig(age=18, role="admin")
cfg.age = 20          # ✅
cfg.role = "user"    # ✅
# cfg.age = -1        # ❌ ValueError
# cfg.role = "guest" # ❌ ValueError
```

## Core API

### `attr(...)`

Declares a descriptor-backed field that validates values on initialization and assignment.

Common parameters:

- `default`: default value
- `default_factory`: lazy default factory (mutually exclusive with `default`)
- `allowlist`: whitelist of allowed values
- `denylist`: blacklist of forbidden values
- `lb` / `ub`: inclusive lower / upper bounds
- `slb` / `sub`: exclusive lower / upper bounds
- `validator`: custom validator function with signature `Callable[[Any], bool]`
- `init` / `repr` / `hash` / `compare` / `kw_only`: forwarded dataclass field behavior controls

Error semantics:

- Misconfiguration at class-definition time (for example, default type mismatch) raises `ValidatorError`
- Invalid runtime values raise `TypeError` or `ValueError`

---

### `@dataclass(...)`

`validating.dataclass` is a compatible enhanced wrapper around `dataclasses.dataclass`.

Enhancements:

1. **Automatic default promotion**: `x: int = 1` is promoted to `attr(default=1)`
2. **Method argument validation**: when `validate_methods=True` (by default `False`), all public methods are wrapped with `validate` (including `@staticmethod` and `@classmethod`)

```python
from validating import dataclass

@dataclass(validate_methods=True)
class Service:
    retries: int = 3

    def run(self, timeout: int) -> int:
        return timeout + self.retries

svc = Service()
svc.run(1)       # ✅
# svc.run("1")   # ❌ TypeError
```

---

### `@validate`

Enables call-time argument validation based on type annotations.

```python
from typing import Literal
from validating import validate

@validate
def configure(mode: Literal["dev", "prod"], workers: int):
    return mode, workers

configure("dev", 4)    # ✅
# configure("test", 4)  # ❌ TypeError
```

`@validate` also handles `assert` statements in validated functions:

- `assert <expr>, "custom message"` keeps the original `AssertionError` with your message.
- `assert <expr>` (without message) is converted to a `ValueError` when `<expr>` is a direct assertion on function arguments, with a message like `expected <expr>, got <value> instead`.
- Assertions that are not direct checks on function arguments are left as regular `AssertionError`.

```python
from validating import validate

@validate
def check_score(score: int) -> int:
    assert score >= 60
    return score

check_score(80)   # ✅
# check_score(59) # ❌ ValueError: expected score >= 60, got 59 instead
```

## More Examples

### 1) `default_factory`

```python
from validating import attr, dataclass

@dataclass
class Cache:
    items: list[int] = attr(default_factory=list)
```

### 2) Complex type hints

```python
from typing import Literal
from validating import attr, dataclass

@dataclass
class AppConfig:
    mode: Literal["dev", "prod"] = attr()
    token: int | str = attr()
    mapping: dict[str, int] = attr()
```

### 3) Custom validator

```python
from validating import attr, dataclass

@dataclass
class EvenNumber:
    value: int = attr(validator=lambda x: x % 2 == 0)
```

## Notes

- Dataclasses with `slots=True` are currently not supported.
- This project focuses on runtime validation and does not replace static type checking.

## See Also

- GitHub: https://github.com/Chitaoji/validating/
- PyPI: https://pypi.org/project/validating/

## License
This project falls under the BSD 3-Clause License.

## History
### v0.0.5

### v0.0.4
* Updated error messages when validating typed dicts.

### v0.0.3
* Improved support for `PEP 585` generics with quoted builtin annotations (for example `list["int"]`) to ensure consistent runtime type validation.

### v0.0.2
* Fixed runtime checking for `TypedDict` and several special typing hints to avoid invalid `isinstance` paths.
* Added runtime validation support for `typing.Unpack`-style annotations.
* Improved forward-reference handling under `TYPE_CHECKING` imports, including deferred annotation resolution and safer fallback behavior when references are temporarily unresolved.
* Refined the `@validate` argument-checking path for better robustness and consistency across annotated call patterns.

### v0.0.1
* Initial release.
