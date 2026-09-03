from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

# SQLModel's AsyncSession, not SQLAlchemy's. They are otherwise identical, but
# only this one keeps .exec(), which returns typed rows for a select(Model).
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import settings

# pool_pre_ping issues a cheap SELECT 1 before handing out a pooled connection.
# Without it, connections dropped by a restarted database or an idle timeout are
# only discovered when a real query fails.
engine = create_async_engine(
    settings.database_url,
    echo=settings.database_echo,
    pool_pre_ping=True,
)

# expire_on_commit=False is close to mandatory in async code. The default expires
# every attribute after commit, so the next attribute read triggers a lazy reload,
# and a lazy reload inside async code raises MissingGreenlet.
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_session() -> AsyncIterator[AsyncSession]:
    """Yield a session for one request, then close it.

    A dependency that yields runs its teardown after the response is produced,
    so the session is guaranteed to close even when the handler raises. Tests
    override this to point at a throwaway database.
    """
    async with AsyncSessionLocal() as session:
        yield session


# Alias so handlers read as `session: SessionDep` rather than repeating the
# Annotated/Depends pair on every route.
SessionDep = Annotated[AsyncSession, Depends(get_session)]
