"""
Database Configuration and Session Management
"""
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    create_async_engine,
    AsyncSession,
    async_sessionmaker
)
from sqlalchemy.orm import declarative_base
from app.config import settings

# Create async engine
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DB_ECHO,
    pool_size=settings.DB_POOL_SIZE,
    max_overflow=settings.DB_MAX_OVERFLOW,
    pool_pre_ping=True,
    pool_recycle=3600,
)

# Create session factory
async_session_maker = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)

# Declarative base for models
Base = declarative_base()


async def get_db():
    """Dependency for getting database session"""
    async with async_session_maker() as session:
        try:
            yield session
        finally:
            await session.close()


async def init_db():
    """Initialize database (create all tables)"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.execute(
            text(
                """
                ALTER TABLE researcher_advisors
                ADD COLUMN IF NOT EXISTS sub_fields_access VARCHAR[] NOT NULL DEFAULT ARRAY[]::VARCHAR[]
                """
            )
        )
        await conn.execute(
            text(
                """
                DO $$
                BEGIN
                    IF NOT EXISTS (
                        SELECT 1
                        FROM pg_type t
                        JOIN pg_enum e ON t.oid = e.enumtypid
                        WHERE t.typname = 'papersource' AND e.enumlabel = 'builtin_library'
                    ) THEN
                        ALTER TYPE papersource ADD VALUE 'builtin_library';
                    END IF;
                END
                $$;
                """
            )
        )
        await conn.execute(
            text(
                """
                ALTER TABLE papers
                ADD COLUMN IF NOT EXISTS collection_slug VARCHAR(120)
                """
            )
        )
        await conn.execute(
            text(
                """
                ALTER TABLE papers
                ADD COLUMN IF NOT EXISTS owner_user_id VARCHAR(36)
                """
            )
        )


async def drop_db():
    """Drop all tables"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

