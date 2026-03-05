# validating

`validating` provides a lightweight `attr()` descriptor factory that adds **runtime validation** to `dataclass` fields.

Key capabilities:

- Type checking (including `Union`, `Literal`, and common container type hints)
- Membership constraints (`allowlist`, `denylist`)
- Boundary checks (`lb`, `ub`, `slb`, `sub`)
- Custom validation logic (`validator`)
- Compatibility with common `dataclasses.field` behaviors (`init`, `repr`, `hash`, `compare`, `kw_only`)
- Also works with non-dataclass classes.
- `validating.dataclass(validate_methods=True)` auto-wraps public methods with `validate()`

## Installation
```sh
$ pip install validating
```

## Quick Start

```python
from dataclasses import dataclass
from validating import attr

@dataclass
class UserConfig:
    age: int = attr(lb=0)
    role: str = attr(allowlist=["admin", "user"])

cfg = UserConfig(age=18, role="admin")
cfg.age = 20           # ✅ valid
cfg.role = "user"     # ✅ valid
# cfg.age = -1          # ❌ ValueError
# cfg.role = "guest"   # ❌ ValueError
```

## API

### `attr(...)`

Declares a `dataclass` field with built-in validation.

Main parameters:

- `default`: default value
- `default_factory`: callable that lazily creates a default value (mutually exclusive with `default`)
- `allowlist`: list of allowed values
- `denylist`: list of forbidden values
- `lb` / `ub`: lower/upper bounds (inclusive)
- `slb` / `sub`: strict lower/upper bounds (exclusive)
- `lb` and `slb` are mutually exclusive; `ub` and `sub` are mutually exclusive
- `validator`: custom validator function with signature `Callable[[Any], bool]`
- `init` / `repr` / `hash` / `compare` / `kw_only`: forwarded to dataclass field behavior controls

Error behavior:

- Misconfiguration at class-definition time (for example: defaults that do not match the annotation) raises `ValidatorError`
- Invalid values during initialization or assignment raise `TypeError` or `ValueError`


### `dataclass(..., validate_methods=False)`

Drop-in replacement for `dataclasses.dataclass` with two additions:

- Plain defaults like `x: int = 1` are promoted to `attr(default=1)` automatically
- When `validate_methods=True`, every method whose name does not start with `_`
  is wrapped by `validate()` (including `@staticmethod` and `@classmethod`)

## More Examples

### 1) `default_factory`

```python
from dataclasses import dataclass
from validating import attr

@dataclass
class Cache:
    items: list[int] = attr(default_factory=list)
```

### 2) Complex type hints

```python
from dataclasses import dataclass
from typing import Literal
from validating import attr

@dataclass
class AppConfig:
    mode: Literal["dev", "prod"] = attr()
    token: int | str = attr()
    mapping: dict[str, int] = attr()
```

### 3) Custom validator

```python
from dataclasses import dataclass
from validating import attr

@dataclass
class EvenNumber:
    value: int = attr(validator=lambda x: x % 2 == 0)
```


## See Also
### Github repository
* https://github.com/Chitaoji/validating/

### PyPI project
* https://pypi.org/project/validating/

## License
This project falls under the BSD 3-Clause License.

## History
### v0.0.1
* Initial release.
