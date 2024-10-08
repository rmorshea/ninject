from __future__ import annotations

from contextlib import AbstractAsyncContextManager
from contextlib import AbstractContextManager
from contextlib import asynccontextmanager as _asynccontextmanager
from contextlib import contextmanager as _contextmanager
from functools import wraps
from typing import TYPE_CHECKING
from typing import Callable
from typing import Generic
from typing import Literal
from typing import ParamSpec
from typing import TypeAlias
from typing import TypeVar

from paramorator import paramorator
from pybooster import injector
from pybooster._private._provider import set_provider
from pybooster._private._utils import get_callable_dependencies
from pybooster._private._utils import get_callable_return_type
from pybooster._private._utils import get_coroutine_return_type
from pybooster._private._utils import get_iterator_yield_type

if TYPE_CHECKING:
    from collections.abc import AsyncIterator
    from collections.abc import Iterator
    from collections.abc import Sequence

    from pybooster.types import AsyncContextManagerCallable
    from pybooster.types import AsyncIteratorCallable
    from pybooster.types import ContextManagerCallable
    from pybooster.types import Dependencies
    from pybooster.types import IteratorCallable

P = ParamSpec("P")
R = TypeVar("R")


@paramorator
def function(
    func: Callable[P, R],
    *,
    dependencies: Dependencies | None = None,
    provides: type[R] | None = None,
) -> SyncProvider[P, R]:
    """Create a provider from the given function.

    Args:
        func: The function to create a provider from.
        dependencies: The dependencies of the function (infered if not provided).
        provides: The type that the function provides (infered if not provided).
    """
    provides = provides or get_callable_return_type(func)

    @wraps(func)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> Iterator[R]:
        yield func(*args, **kwargs)

    return iterator(wrapper, provides=provides, dependencies=dependencies)


@paramorator
def asyncfunction(
    func: Callable[P, R],
    *,
    dependencies: Dependencies | None = None,
    provides: type[R] | None = None,
) -> AsyncProvider[P, R]:
    """Create a provider from the given coroutine.

    Args:
        func: The function to create a provider from.
        dependencies: The dependencies of the function (infered if not provided).
        provides: The type that the function provides (infered if not provided).
    """
    provides = provides or get_coroutine_return_type(func)

    @wraps(func)
    async def wrapper(*args: P.args, **kwargs: P.kwargs) -> AsyncIterator[R]:
        yield await func(*args, **kwargs)

    return asynciterator(wrapper, provides=provides, dependencies=dependencies)


@paramorator
def iterator(
    func: IteratorCallable[P, R],
    *,
    dependencies: Dependencies | None = None,
    provides: type[R] | None = None,
) -> SyncProvider[P, R]:
    """Create a provider from the given iterator function.

    Args:
        func: The function to create a provider from.
        dependencies: The dependencies of the function (infered if not provided).
        provides: The type that the function provides (infered if not provided).
    """
    provides = provides or get_iterator_yield_type(func, sync=True)
    norm_dependencies = get_callable_dependencies(func, dependencies)
    return _SyncProvider(
        injector.contextmanager(func, dependencies=norm_dependencies) if norm_dependencies else _contextmanager(func),
        provides,
        set(norm_dependencies.values()),
    )


@paramorator
def asynciterator(
    func: AsyncIteratorCallable[P, R],
    *,
    dependencies: Dependencies | None = None,
    provides: type[R] | None = None,
) -> AsyncProvider[P, R]:
    """Create a provider from the given async iterator function.

    Args:
        func: The function to create a provider from.
        dependencies: The dependencies of the function (infered if not provided).
        provides: The type that the function provides (infered if not provided).
    """
    provides = provides or get_iterator_yield_type(func, sync=False)
    norm_dependencies = get_callable_dependencies(func, dependencies)
    return _AsyncProvider(
        (
            injector.asynccontextmanager(func, dependencies=norm_dependencies)
            if norm_dependencies
            else _asynccontextmanager(func)
        ),
        provides,
        set(norm_dependencies.values()),
    )


class _Provider(Generic[P, R]):

    provides: type[R]
    """The dependency that this provider produces."""
    value: ContextManagerCallable[P, R] | AsyncContextManagerCallable[P, R]
    """The function that produces the dependency."""

    _dependency_set: set[Sequence[type]]
    _sync: bool

    @_contextmanager
    def scope(self, *args: P.args, **kwargs: P.kwargs) -> Iterator[None]:
        """Declare this as the provider for the dependency within the context.

        Noteable this does not actually create the dependency until the context is entered.
        """
        reset = set_provider(
            self.provides,
            wraps(self.value)(lambda: self.value(*args, **kwargs)),
            self._dependency_set,
            sync=self._sync,
        )
        try:
            yield None
        finally:
            reset()


class _SyncProvider(_Provider[P, R]):

    def __init__(
        self,
        manager: ContextManagerCallable[P, R],
        provides: type[R],
        dependency_set: set[Sequence[type]],
    ) -> None:
        self.provides = provides
        self.value: Callable[P, AbstractContextManager[R]] = manager
        self._dependency_set = dependency_set
        self._sync: Literal[True] = True


class _AsyncProvider(_Provider[P, R]):

    def __init__(
        self,
        manager: AsyncContextManagerCallable[P, R],
        provides: type[R],
        dependency_set: set[Sequence[type]],
    ) -> None:
        self.provides = provides
        self.value: Callable[P, AbstractAsyncContextManager[R]] = manager
        self._dependency_set = dependency_set
        self._sync: Literal[False] = False


SyncProvider: TypeAlias = "_SyncProvider[P, R]"
"""A sync provider that produces a dependency."""
AsyncProvider: TypeAlias = "_AsyncProvider[P, R]"
"""An async provider that produces a dependency."""
Provider: TypeAlias = "SyncProvider[P, R] | AsyncProvider[P, R]"
"""A provider that produces a dependency."""
