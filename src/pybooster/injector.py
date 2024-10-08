from __future__ import annotations

from contextlib import AbstractAsyncContextManager
from contextlib import AbstractContextManager
from contextlib import AsyncExitStack
from contextlib import ExitStack
from contextlib import asynccontextmanager as _asynccontextmanager
from contextlib import contextmanager as _contextmanager
from functools import wraps
from typing import TYPE_CHECKING
from typing import Any
from typing import Callable
from typing import Literal
from typing import ParamSpec
from typing import TypeVar

from paramorator import paramorator
from pybooster._private._injector import async_update_arguments_by_initializing_dependencies
from pybooster._private._injector import setdefault_arguments_with_initialized_dependencies
from pybooster._private._injector import sync_update_arguments_by_initializing_dependencies
from pybooster._private._utils import get_callable_dependencies
from pybooster._private._utils import normalize_dependency

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator
    from collections.abc import Coroutine
    from collections.abc import Generator
    from collections.abc import Sequence

    from pybooster.types import AsyncGeneratorCallable
    from pybooster.types import AsyncIteratorCallable
    from pybooster.types import Dependencies
    from pybooster.types import GeneratorCallable
    from pybooster.types import IteratorCallable

P = ParamSpec("P")
R = TypeVar("R")
Y = TypeVar("Y")
S = TypeVar("S")


@paramorator
def function(
    func: Callable[P, R],
    *,
    dependencies: Dependencies | None = None,
) -> Callable[P, R]:
    """Inject dependencies into the given function.

    Args:
        func: The function to inject dependencies into.
        dependencies: The dependencies to inject into the function.
    """
    dependencies = get_callable_dependencies(func, dependencies)

    @wraps(func)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
        if not (missing := setdefault_arguments_with_initialized_dependencies(kwargs, dependencies)):
            return func(*args, **kwargs)
        with ExitStack() as stack:
            sync_update_arguments_by_initializing_dependencies(stack, kwargs, missing)
            return func(*args, **kwargs)

    return wrapper


@paramorator
def asyncfunction(
    func: Callable[P, Coroutine[Any, Any, R]],
    *,
    dependencies: Dependencies | None = None,
) -> Callable[P, Coroutine[Any, Any, R]]:
    """Inject dependencies into the given coroutine."""
    dependencies = get_callable_dependencies(func, dependencies)

    @wraps(func)
    async def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
        if not (missing := setdefault_arguments_with_initialized_dependencies(kwargs, dependencies)):
            return await func(*args, **kwargs)
        async with AsyncExitStack() as stack:
            await async_update_arguments_by_initializing_dependencies(stack, kwargs, missing)
            return await func(*args, **kwargs)

    return wrapper


@paramorator
def generator(
    func: GeneratorCallable[P, Y, S, R],
    *,
    dependencies: Dependencies | None = None,
) -> GeneratorCallable[P, Y, S, R]:
    """Inject dependencies into the given iterator."""
    dependencies = get_callable_dependencies(func, dependencies)

    @wraps(func)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> Generator[Y, S, R]:
        if not (missing := setdefault_arguments_with_initialized_dependencies(kwargs, dependencies)):
            yield from func(*args, **kwargs)
            return
        with ExitStack() as stack:
            sync_update_arguments_by_initializing_dependencies(stack, kwargs, missing)
            yield from func(*args, **kwargs)

    return wrapper


@paramorator
def asyncgenerator(
    func: AsyncGeneratorCallable[P, Y, S],
    *,
    dependencies: Dependencies | None = None,
) -> AsyncGeneratorCallable[P, Y, S]:
    """Inject dependencies into the given async iterator."""
    dependencies = get_callable_dependencies(func, dependencies)

    @wraps(func)
    async def wrapper(*args: P.args, **kwargs: P.kwargs) -> AsyncGenerator[Y, S]:
        if not (missing := setdefault_arguments_with_initialized_dependencies(kwargs, dependencies)):
            async for value in func(*args, **kwargs):
                yield value
            return
        async with AsyncExitStack() as stack:
            await async_update_arguments_by_initializing_dependencies(stack, kwargs, missing)
            async for value in func(*args, **kwargs):
                yield value
            return

    return wrapper


@paramorator
def contextmanager(
    func: IteratorCallable[P, R],
    *,
    dependencies: Dependencies | None = None,
) -> AbstractContextManager[R]:
    """Inject dependencies into the given context manager function."""
    return _contextmanager(generator(func, dependencies=dependencies))


@paramorator
def asynccontextmanager(
    func: AsyncIteratorCallable[P, R],
    *,
    dependencies: Dependencies | None = None,
) -> AbstractAsyncContextManager[R]:
    """Inject dependencies into the given async context manager function."""
    return _asynccontextmanager(asyncgenerator(func, dependencies=dependencies))


def current(cls: type[R]) -> _CurrentContext[R]:
    """Get the current value of a dependency."""
    return _CurrentContext(normalize_dependency(cls))


class _CurrentContext(AbstractContextManager[R], AbstractAsyncContextManager[R]):
    """A context manager to provide the current value of a dependency."""

    def __init__(self, types: Sequence[type[R]]) -> None:
        self.types = types

    def __enter__(self) -> R:
        if hasattr(self, "_sync_stack"):
            msg = "Cannot reuse a context manager."
            raise RuntimeError(msg)

        values: dict[Literal["dependency"], R] = {}
        if not (missing := setdefault_arguments_with_initialized_dependencies(values, {"dependency": self.types})):
            return values["dependency"]

        stack = self._sync_stack = ExitStack()

        sync_update_arguments_by_initializing_dependencies(stack, values, missing)
        return values["dependency"]

    async def __aenter__(self) -> R:
        if hasattr(self, "_async_stack"):
            msg = "Cannot reuse a context manager."
            raise RuntimeError(msg)

        values: dict[Literal["dependency"], R] = {}
        if not (missing := setdefault_arguments_with_initialized_dependencies(values, {"dependency": self.types})):
            return values["dependency"]

        stack = self._async_stack = ExitStack()

        await async_update_arguments_by_initializing_dependencies(stack, values, missing)
        return values["dependency"]

    def __exit__(self, *exc: Any) -> None:
        if hasattr(self, "_sync_stack"):
            try:
                self._sync_stack.__exit__(*exc)
            finally:
                del self._sync_stack

    async def __aexit__(self, *exc: Any) -> None:
        if hasattr(self, "_async_stack"):
            try:
                await self._async_stack.__aexit__(*exc)
            finally:
                del self._async_stack
