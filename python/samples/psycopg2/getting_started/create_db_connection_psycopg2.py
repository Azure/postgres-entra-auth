"""
Sample demonstrating both synchronous and asynchronous psycopg2 connections 
with Azure Entra ID authentication for Azure PostgreSQL.

This example shows:
1. Synchronous connection using psycopg2 with Entra ID authentication
2. Asynchronous connection using aiopg with Entra ID authentication

Both examples use the same Azure Entra ID authentication mechanism to connect
to Azure Database for PostgreSQL.
"""

from dotenv import load_dotenv
import argparse
import asyncio
import sys
import os
from psycopg2 import pool
from azurepg_entra.psycopg2 import connect_with_entra, connect_with_entra_async
from async_pool_utils import AsyncEntraConnectionPool

# Load environment variables from .env file
load_dotenv()
SERVER = os.getenv("POSTGRES_SERVER")
DATABASE = os.getenv("POSTGRES_DATABASE", "postgres")

def main_sync():
    """Synchronous connection example using psycopg2 with Entra ID authentication and connection pooling."""

    try:
        # Create a wrapper function that explicitly passes our server parameters
        def entra_connection_factory(*args, **kwargs):
            # Ignore any arguments passed by ThreadedConnectionPool and use our explicit parameters
            return connect_with_entra(
                host=SERVER,
                port=5432,
                dbname=DATABASE
            )
        
        # Create a connection pool using psycopg2 with Entra ID authentication
        connection_pool = pool.ThreadedConnectionPool(
            minconn=1,
            maxconn=5,
            connection_factory=entra_connection_factory
        )

        # Get a connection from the pool
        conn = connection_pool.getconn()
        
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT now()")
                result = cur.fetchone()
                print(f"Sync - Database time: {result[0]}")
                
                # Test current user query
                cur.execute("SELECT current_user")
                user = cur.fetchone()
                print(f"Sync - Connected as: {user[0]}")
        finally:
            # Return connection to pool
            connection_pool.putconn(conn)
            connection_pool.closeall()
            
    except Exception as e:
        print(f"Sync - Error connecting to database: {e}")
        raise

async def main_async():
    """Asynchronous connection example with custom async pool using connection_factory pattern."""

    try:
        # Create async connection factory function (mirrors the sync version)
        async def entra_async_connection_factory(*args, **kwargs):
            # Ignore any arguments and use our explicit parameters
            return await connect_with_entra_async(
                host=SERVER,
                port=5432,
                dbname=DATABASE
            )
        
        # Use our custom async pool with connection factory
        async with AsyncEntraConnectionPool(entra_async_connection_factory, minconn=1, maxconn=5) as connection_pool:
            # Get a connection from the pool (mirrors sync pattern)
            conn = await connection_pool.getconn()
            
            try:
                async with conn.cursor() as cur:
                    await cur.execute("SELECT now()")
                    result = await cur.fetchone()
                    print(f"Async - Database time: {result[0]}")
                    
                    # Test current user query
                    await cur.execute("SELECT current_user")
                    user = await cur.fetchone()
                    print(f"Async - Connected as: {user[0]}")
            finally:
                # Return connection to pool (mirrors sync pattern)
                connection_pool.putconn(conn)
                    
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
        description="Demonstrate psycopg2/aiopg connections with Azure Entra ID authentication"
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