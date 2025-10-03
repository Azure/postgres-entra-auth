"""
Sample demonstrating both synchronous and asynchronous psycopg connections 
with Azure Entra ID authentication for Azure PostgreSQL.

This example shows:
1. Synchronous connection using SyncEntraConnection and ConnectionPool
2. Asynchronous connection using AsyncEntraConnection and AsyncConnectionPool

Both examples use the same Azure Entra ID authentication mechanism to connect
to Azure Database for PostgreSQL.
"""

from psycopg_pool import AsyncConnectionPool, ConnectionPool
from dotenv import load_dotenv
import argparse
import asyncio
import sys
import os
from azurepg_entra.psycopg3 import SyncEntraConnection, AsyncEntraConnection

# Load environment variables from .env file
load_dotenv()
SERVER = os.getenv("POSTGRES_SERVER")
DATABASE = os.getenv("POSTGRES_DATABASE", "postgres")

def main_sync():
    """Synchronous connection example using psycopg with Entra ID authentication."""

    try:
        pool = ConnectionPool(
            conninfo=f"postgresql://{SERVER}:5432/{DATABASE}",
            min_size=1,
            max_size=5,
            open=False,
            connection_class=SyncEntraConnection
        )
        pool.open()
        with pool, pool.connection() as conn, conn.cursor() as cur:
            cur.execute("SELECT now()")
            result = cur.fetchone()
            print(f"Sync - Database time: {result}")
            
            # Test current user query
            cur.execute("SELECT current_user")
            user = cur.fetchone()
            print(f"Sync - Connected as: {user[0]}")
    except Exception as e:
        print(f"Sync - Error connecting to database: {e}")
        raise

async def main_async():
    """Asynchronous connection example using psycopg with Entra ID authentication."""

    try:
        pool = AsyncConnectionPool(
            conninfo=f"postgresql://{SERVER}:5432/{DATABASE}",
            min_size=1,
            max_size=5,
            open=False,
            connection_class=AsyncEntraConnection
        )
        await pool.open()
        async with pool, pool.connection() as conn, conn.cursor() as cur:
            await cur.execute("SELECT now()")
            result = await cur.fetchone()
            print(f"Async - Database time: {result}")
            
            # Test current user query
            await cur.execute("SELECT current_user")
            user = await cur.fetchone()
            print(f"Async - Connected as: {user[0]}")
    except Exception as e:
        print(f"Async - Error connecting to database: {e}")
        raise

async def main(mode: str = "both"):
    """Main function that runs sync and/or async examples based on mode.
    
    Args:
        mode: "sync", "async", or "both" to determine which examples to run
    """
    if mode in ("sync", "both"):
        print("=== Running Synchronous Example ===")
        try:
            main_sync()
            print("✅ Sync example completed successfully!")
        except Exception as e:
            print(f"❌ Sync example failed: {e}")
    
    if mode in ("async", "both"):
        if mode == "both":
            print("\n=== Running Asynchronous Example ===")
        else:
            print("=== Running Asynchronous Example ===")
        try:
            await main_async()
            print("✅ Async example completed successfully!")
        except Exception as e:
            print(f"❌ Async example failed: {e}")

if __name__ == "__main__":
    # Parse command line arguments
    parser = argparse.ArgumentParser(
        description="Demonstrate psycopg connections with Azure Entra ID authentication"
    )
    parser.add_argument(
        "--mode",
        choices=["sync", "async", "both"],
        default="both",
        help="Run synchronous, asynchronous, or both examples (default: both)"
    )
    args = parser.parse_args()
    
    # Set Windows event loop policy for compatibility if needed
    if sys.platform.startswith('win'):
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    
    asyncio.run(main(args.mode))