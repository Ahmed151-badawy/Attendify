"""
verify_neon.py
──────────────
Standalone utility script to test async connectivity to the Neon cluster.
Run with: python verify_neon.py
"""
import asyncio
from sqlalchemy import text
from app.core.database import engine

async def check_connectivity():
    print("📡 Attempting async connection to Neon Postgres...")
    try:
        async with engine.connect() as conn:
            # 1. Run a basic low-level ping
            result = await conn.execute(text("SELECT 1;"))
            ping = result.scalar()
            if ping == 1:
                print("✅ Database connectivity handshake successful!")
            
            # 2. Inspect active table schema availability
            print("\n🔍 Checking for live tables in the public schema...")
            table_query = text(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema = 'public';"
            )
            table_result = await conn.execute(table_query)
            tables = table_result.scalars().all()
            
            if tables:
                print(f"Found {len(tables)} active tables:")
                for table in tables:
                    print(f"  ──> {table}")
            else:
                print("⚠️ Connection works, but no tables were found in the 'public' schema.")
                
    except Exception as e:
        print(f"❌ Database connection failed!")
        print(f"Details: {e}")
    finally:
        # Clean up the engine thread pool
        await engine.dispose()

if __name__ == "__main__":
    asyncio.run(check_connectivity())