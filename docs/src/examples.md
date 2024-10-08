# Examples

## [SQLite](https://docs.python.org/3/library/sqlite3.html)

```python
import sqlite3
from typing import Iterator

from pybooster import injector
from pybooster import provider
from pybooster import required


@provider.iterator
def sqlite_connection(database: str) -> Iterator[sqlite3.Connection]:
    with sqlite3.connect(database) as conn:
        yield conn


@injector.function
def query_database(query: str, *, conn: sqlite3.Connection = required) -> None:
    conn.execute(query)


with sqlite_connection.scope(":memory:"):
    query_database("CREATE TABLE example (id INTEGER PRIMARY KEY)")
```

## [SQLAlchemy](https://www.sqlalchemy.org/)

```python
from collections.abc import Iterator

from sqlalchemy import Engine
from sqlalchemy import create_engine
from sqlalchemy import select
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import Session
from sqlalchemy.orm import mapped_column

from pybooster import injector
from pybooster import provider
from pybooster import required
from pybooster import shared


class Base(DeclarativeBase): ...


class User(Base):
    __tablename__ = "user"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str]


@provider.iterator
def sqlalchemy_engine(url: str) -> Iterator[Engine]:
    engine = create_engine(url)
    try:
        yield engine
    finally:
        engine.dispose()


@provider.iterator
def sqlalchemy_session(*, engine: Engine = required) -> Iterator[Session]:
    with Session(bind=engine, expire_on_commit=False) as session, session.begin():
        yield session


@injector.function
def create_tables(*, session: Session = required) -> None:
    Base.metadata.create_all(session.bind)


@injector.function
def add_user(name: str, *, session: Session = required) -> int:
    user = User(name=name)
    session.add(user)
    session.flush()
    return user.id


@injector.function
def get_user(user_id: int, *, session: Session = required) -> User:
    return session.execute(select(User).where(User.id == user_id)).scalar_one()


url = "sqlite:///:memory:"
with (
    sqlalchemy_engine.scope(url),
    sqlalchemy_session.scope(),
    shared(Engine),
):
    create_tables()
    user_id = add_user("Alice")
    user = get_user(user_id)
    assert user.name == "Alice"
```

## [SQLAlchemy (Async)](https://www.sqlalchemy.org/)

```python
import asyncio
from collections.abc import AsyncIterator

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column

from pybooster import injector
from pybooster import provider
from pybooster import required
from pybooster import shared


class Base(DeclarativeBase): ...


class User(Base):
    __tablename__ = "user"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str]


@provider.asynciterator
async def sqlalchemy_async_engine(url: str) -> AsyncIterator[AsyncEngine]:
    engine = create_async_engine(url)
    try:
        yield engine
    finally:
        await engine.dispose()


@provider.asynciterator
async def sqlalchemy_async_session(
    *, engine: AsyncEngine = required
) -> AsyncIterator[AsyncSession]:
    async with (
        AsyncSession(bind=engine, expire_on_commit=False) as session,
        session.begin(),
    ):
        yield session


@injector.asyncfunction
async def create_tables(*, engine: AsyncEngine = required) -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


@injector.asyncfunction
async def add_user(name: str, *, session: AsyncSession = required) -> int:
    user = User(name=name)
    session.add(user)
    await session.flush()
    return user.id


@injector.asyncfunction
async def get_user(user_id: int, *, session: AsyncSession = required) -> User:
    return (await session.execute(select(User).where(User.id == user_id))).scalar_one()


async def main():
    url = "sqlite+aiosqlite:///:memory:"
    with sqlalchemy_async_engine.scope(url), sqlalchemy_async_session.scope():
        async with shared(AsyncEngine):
            await create_tables()
            user_id = await add_user("Alice")
            user = await get_user(user_id)
            assert user.name == "Alice"


asyncio.run(main())
```
