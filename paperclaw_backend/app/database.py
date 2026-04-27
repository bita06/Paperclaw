"""
Database Configuration and Session Management
"""
from pgvector.asyncpg import register_vector
from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import declarative_base

from app.config import settings

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DB_ECHO,
    pool_size=settings.DB_POOL_SIZE,
    max_overflow=settings.DB_MAX_OVERFLOW,
    pool_pre_ping=True,
    pool_recycle=3600,
)


@event.listens_for(engine.sync_engine, "connect")
def register_pgvector(dbapi_connection, connection_record):
    dbapi_connection.run_async(register_vector)


async_session_maker = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)

Base = declarative_base()

from app import models  # noqa: E402,F401


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
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
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
        await conn.execute(text("ALTER TABLE papers ADD COLUMN IF NOT EXISTS collection_slug VARCHAR(120)"))
        await conn.execute(text("ALTER TABLE papers ADD COLUMN IF NOT EXISTS owner_user_id VARCHAR(36)"))
        await conn.execute(text("ALTER TABLE paper_sections ADD COLUMN IF NOT EXISTS page_start INTEGER"))
        await conn.execute(text("ALTER TABLE paper_sections ADD COLUMN IF NOT EXISTS page_end INTEGER"))
        await conn.execute(text("ALTER TABLE paper_chunks ADD COLUMN IF NOT EXISTS page_start INTEGER"))
        await conn.execute(text("ALTER TABLE paper_chunks ADD COLUMN IF NOT EXISTS page_end INTEGER"))
        await conn.execute(text("ALTER TABLE paper_chunks ADD COLUMN IF NOT EXISTS chunk_tsv tsvector"))
        await conn.execute(
            text(
                """
                DO $$
                DECLARE current_type TEXT;
                BEGIN
                    SELECT format_type(a.atttypid, a.atttypmod)
                    INTO current_type
                    FROM pg_attribute a
                    JOIN pg_class c ON a.attrelid = c.oid
                    JOIN pg_namespace n ON c.relnamespace = n.oid
                    WHERE c.relname = 'paper_chunks'
                      AND n.nspname = 'public'
                      AND a.attname = 'chunk_embedding'
                      AND a.attnum > 0
                      AND NOT a.attisdropped;

                    IF current_type IS NULL THEN
                        ALTER TABLE paper_chunks
                        ADD COLUMN chunk_embedding vector(1536);
                    ELSIF current_type <> 'vector(1536)' THEN
                        ALTER TABLE paper_chunks
                        ALTER COLUMN chunk_embedding TYPE vector(1536)
                        USING CASE
                            WHEN chunk_embedding IS NULL THEN NULL
                            ELSE chunk_embedding::vector(1536)
                        END;
                    END IF;
                END
                $$;
                """
            )
        )
        await conn.execute(
            text(
                """
                CREATE OR REPLACE FUNCTION update_paper_chunk_tsv() RETURNS trigger AS $$
                BEGIN
                    NEW.chunk_tsv :=
                        setweight(to_tsvector('simple', coalesce(NEW.section_title, '')), 'A') ||
                        setweight(to_tsvector('simple', coalesce(NEW.chunk_text, '')), 'B');
                    RETURN NEW;
                END
                $$ LANGUAGE plpgsql;
                """
            )
        )
        await conn.execute(
            text(
                """
                DROP TRIGGER IF EXISTS trg_update_paper_chunk_tsv ON paper_chunks;
                """
            )
        )
        await conn.execute(
            text(
                """
                CREATE TRIGGER trg_update_paper_chunk_tsv
                BEFORE INSERT OR UPDATE OF section_title, chunk_text
                ON paper_chunks
                FOR EACH ROW
                EXECUTE FUNCTION update_paper_chunk_tsv();
                """
            )
        )
        await conn.execute(
            text(
                """
                UPDATE paper_chunks
                SET chunk_tsv =
                    setweight(to_tsvector('simple', coalesce(section_title, '')), 'A') ||
                    setweight(to_tsvector('simple', coalesce(chunk_text, '')), 'B')
                WHERE chunk_tsv IS NULL;
                """
            )
        )
        await conn.execute(
            text(
                """
                CREATE INDEX IF NOT EXISTS ix_paper_chunks_chunk_embedding_hnsw
                ON paper_chunks
                USING hnsw (chunk_embedding vector_cosine_ops)
                """
            )
        )
        await conn.execute(
            text(
                """
                CREATE INDEX IF NOT EXISTS ix_paper_chunks_chunk_tsv_gin
                ON paper_chunks
                USING gin (chunk_tsv)
                """
            )
        )


async def drop_db():
    """Drop all tables"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
