"""
Database initialization script
"""
import asyncio
from app.database import init_db, drop_db


async def main():
    print("🔄 Initializing database...")
    try:
        await init_db()
        print("✅ Database initialized successfully!")
    except Exception as e:
        print(f"❌ Error initializing database: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())
