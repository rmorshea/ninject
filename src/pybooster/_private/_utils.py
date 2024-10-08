from __future__ import annotations

import builtins
from collections.abc import AsyncIterator
from collections.abc import Coroutine
from collections.abc import Iterator
from collections.abc import Mapping
from collections.abc import Sequence
from inspect import Parameter
from inspect import signature
from types import UnionType
from typing import TYPE_CHECKING
from typing import Any
from typing import Callable
from typing import ParamSpec
from typing import TypedDict
from typing import TypeVar
from typing import get_args
from typing import get_origin
from typing import get_type_hints

import pybooster

if TYPE_CHECKING:
    from pybooster.types import Dependencies

P = ParamSpec("P")
R = TypeVar("R")
C = TypeVar("C", bound=Callable)
D = TypeVar("D", bound=Callable)


def make_sentinel_value(module: str, name: str) -> Any:
    return type(name, (), {"__repr__": lambda _: f"{module}.{name}"})()


undefined = make_sentinel_value(__name__, "undefined")
"""Represents an undefined default."""

NormDependencies = Mapping[str, Sequence[type]]
"""Dependencies normalized to a mapping of parameter names to their possible types."""


def get_callable_dependencies(func: Callable, dependencies: Dependencies | None = None) -> NormDependencies:
    if dependencies is not None:
        return {name: cls if isinstance(cls, Sequence) else (cls,) for name, cls in dependencies.items()}
    return _get_callable_dependencies(func)


def _get_callable_dependencies(func: Callable[P, R]) -> NormDependencies:
    dependencies: dict[str, Sequence[type]] = {}
    hints = get_type_hints(func, include_extras=True)
    for param in signature(func).parameters.values():
        if param.default is pybooster.required:
            if param.kind is not Parameter.KEYWORD_ONLY:
                msg = f"Expected dependant parameter {param!r} to be keyword-only."
                raise TypeError(msg)
            dependencies[param.name] = normalize_dependency(hints[param.name])
    return dependencies


def normalize_dependency(types: type[R] | Sequence[type[R]]) -> Sequence[type[R]]:
    if isinstance(types, Sequence):
        return [c for cls in types for c in normalize_dependency(cls)]

    cls = types
    if isinstance(cls, type) and cls.__module__ == "builtins" and getattr(builtins, cls.__name__, None) is cls:
        msg = f"Cannot provide built-in type {cls.__module__}.{cls} - use NewType to make a distinct subtype."
        raise TypeError(msg)

    return normalize_dependency(get_args(cls)) if get_origin(cls) is UnionType else (cls,)


class DependencyInfo(TypedDict):
    type: type
    new: bool


def get_callable_return_type(func: Callable) -> type:
    hints = get_type_hints(func)

    if (return_type := hints.get("return")) is None:
        msg = f"Expected function {func} to have a return type"
        raise TypeError(msg)

    return return_type


def get_coroutine_return_type(func: Callable) -> type:
    return_type = get_callable_return_type(func)
    if get_origin(return_type) is Coroutine:
        try:
            return get_args(return_type)[2]
        except IndexError:
            msg = f"Expected return type {return_type} to have three arguments"
            raise TypeError(msg) from None
    else:
        return return_type


def get_iterator_yield_type(func: Callable, *, sync: bool) -> type:
    return_type = get_callable_return_type(func)
    if sync:
        if get_origin(return_type) is not Iterator:
            msg = f"Expected return type {return_type} to be an iterator"
            raise TypeError(msg)
    else:
        if get_origin(return_type) is not AsyncIterator:
            msg = f"Expected return type {return_type} to be an async iterator"
            raise TypeError(msg)
    try:
        return get_args(return_type)[0]
    except IndexError:
        msg = f"Expected return type {return_type} to have a single argument"
        raise TypeError(msg) from None
