from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase
from db.config import settings

class Base(DeclarativeBase):
    pass

engine = create_async_engine(str(settings.DATABASE_URL), echo=False, pool_pre_ping=True)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

async def init_db() -> None:
    async with engine.begin() as conn:
        # Import models here to ensure metadata is populated
        from entities.photo import Photo  # noqa: F401
        await conn.run_sync(Base.metadata.create_all)