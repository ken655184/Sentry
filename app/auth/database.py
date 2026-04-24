"""認證 DB 連線 (SQLite + SQLAlchemy async)"""
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import settings


class Base(DeclarativeBase):
    pass


engine = create_async_engine(
    settings.AUTH_DB_URL,
    echo=settings.DEBUG,
    future=True,
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


async def init_auth_db() -> None:
    """首次啟動建立資料表"""
    # 先 import models 讓 SQLAlchemy 認得
    from app.auth import models  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_auth_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI 相依注入用"""
    async with AsyncSessionLocal() as session:
        yield session
