"""Idempotent pgvector migration for PaperChunk embeddings.

Run from paperclaw_backend:
    .\\venv\\Scripts\\python.exe -m scripts.migrate_pgvector_chunks
"""

import asyncio

from sqlalchemy import text

from app.config import settings
from app.database import engine


async def migrate_pgvector_chunks() -> None:
    async with engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.execute(
            text(
                f"""
                ALTER TABLE paper_chunks
                ALTER COLUMN chunk_embedding TYPE vector({settings.EMBEDDING_DIMENSION})
                USING CASE
                    WHEN chunk_embedding IS NULL THEN NULL
                    ELSE chunk_embedding::vector({settings.EMBEDDING_DIMENSION})
                END
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


async def main() -> None:
    await migrate_pgvector_chunks()
    await engine.dispose()
    print("pgvector paper_chunks migration ok")


if __name__ == "__main__":
    asyncio.run(main())

