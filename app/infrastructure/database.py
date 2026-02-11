from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from app.config import settings

DATABASE_URL = str(settings.database_url).replace("postgresql://", "postgresql+asyncpg://")

engine = create_async_engine(DATABASE_URL, echo=False, future=True)

async_session_factory = sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)

async def get_db_session() -> AsyncSession:
    async with async_session_factory() as session:
        yield session

async def init_db():
    from sqlmodel import SQLModel
    # Import tables to ensure they are registered with SQLModel.metadata
    from app.infrastructure.tables import PublicRepo
    
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
