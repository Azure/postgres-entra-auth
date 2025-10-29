"""
Sample demonstrating everlasting synchronous and asynchronous psycopg3 connections
with Azure Entra ID authentication for Azure PostgreSQL that run queries indefinitely
to test token refresh capabilities.
"""

import argparse
import asyncio
import os
import sys
import time
from datetime import datetime

from dotenv import load_dotenv
from psycopg_pool import AsyncConnectionPool, ConnectionPool

from azurepg_entra.psycopg3 import AsyncEntraConnection, EntraConnection

# Load environment variables from .env file
load_dotenv()
SERVER = os.getenv("POSTGRES_SERVER")
DATABASE = os.getenv("POSTGRES_DATABASE", "postgres")


def run_everlasting_sync_queries(interval_minutes: int = 2) -> None:
    """Run synchronous database queries indefinitely with psycopg3 and Entra authentication."""

    print("=== Running Everlasting Synchronous psycopg3 Connection Example ===")
    print(f"Running queries every {interval_minutes} minutes...")
    print("Press Ctrl+C to stop\n")

    # We use the EntraConnection class to enable synchronous Entra-based authentication for database access.
    # This class is applied whenever the connection pool creates a new connection, ensuring that Entra
    # authentication tokens are properly managed and refreshed so that each connection uses a valid token.
    #
    # For more details, see: https://www.psycopg.org/psycopg3/docs/api/connections.html#psycopg.Connection.connect
    pool = ConnectionPool(
        conninfo=f"postgresql://{SERVER}:5432/{DATABASE}",
        min_size=1,
        max_size=3,
        open=False,
        connection_class=EntraConnection,
    )

    execution_count = 0
    with pool:
        # Get connection from pool
        conn = pool.getconn()
        while True:
            execution_count += 1
            current_time = datetime.now().strftime("%H:%M:%S")
            print(f"Sync Execution #{execution_count} at {current_time}")
            with conn.cursor() as cur:
                # Query 1: Get PostgreSQL version
                cur.execute("SELECT version()")
                version = cur.fetchone()
                print(
                    f"Connected to PostgreSQL: {version[0][:50] if version else 'Unknown'}..."
                )

                # Query 2: Get current user
                cur.execute("SELECT current_user")
                user = cur.fetchone()
                print(f"Connected as: {user[0] if user else 'Unknown'}")

                # Query 3: Get current timestamp
                cur.execute("SELECT now()")
                timestamp = cur.fetchone()
                print(f"Server time: {timestamp[0] if timestamp else 'Unknown'}")

                print("Sync query execution successful!")

            print(f"Waiting {interval_minutes} minutes until next execution...\n")
            time.sleep(interval_minutes * 60)


async def run_everlasting_async_queries(interval_minutes: int = 2) -> None:
    """Run asynchronous database queries indefinitely with psycopg3 and Entra authentication."""

    print("=== Running Everlasting Asynchronous psycopg3 Connection Example ===")
    print(f"Running queries every {interval_minutes} minutes...")
    print("Press Ctrl+C to stop\n")

    # We use the AsyncEntraConnection class to enable asynchronous Entra-based authentication for database access.
    # This class is applied whenever the connection pool creates a new connection, ensuring that Entra
    # authentication tokens are properly managed and refreshed so that each connection uses a valid token.
    #
    # For more details, see: https://www.psycopg.org/psycopg3/docs/api/connections.html#psycopg.Connection.connect
    pool = AsyncConnectionPool(
        conninfo=f"postgresql://{SERVER}:5432/{DATABASE}",
        min_size=1,
        max_size=3,
        open=False,
        connection_class=AsyncEntraConnection,
    )

    execution_count = 0
    async with pool:
        # Get connection from pool
        conn = await pool.getconn()
        while True:
            execution_count += 1
            current_time = datetime.now().strftime("%H:%M:%S")

            print(f"Async Execution #{execution_count} at {current_time}")
            async with conn.cursor() as cur:
                # Query 1: Get PostgreSQL version
                await cur.execute("SELECT version()")
                version = await cur.fetchone()
                print(
                    f"Connected to PostgreSQL: {version[0][:50] if version else 'Unknown'}..."
                )

                # Query 2: Get current user
                await cur.execute("SELECT current_user")
                user = await cur.fetchone()
                print(f"Connected as: {user[0] if user else 'Unknown'}")

                # Query 3: Get current timestamp
                await cur.execute("SELECT now()")
                timestamp = await cur.fetchone()
                print(f"Server time: {timestamp[0] if timestamp else 'Unknown'}")

                print("Async query execution successful!")

            print(f"Waiting {interval_minutes} minutes until next execution...\n")
            time.sleep(interval_minutes * 60)


async def main() -> None:
    """Main function with command line argument parsing."""
    parser = argparse.ArgumentParser(
        description="Demonstrate everlasting psycopg3 connections with Azure Entra ID authentication"
    )
    parser.add_argument(
        "--mode",
        choices=["sync", "async", "both"],
        default="both",
        help="Run synchronous, asynchronous, or both examples (default: both)",
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=2,
        help="Query execution interval in minutes (default: 2)",
    )
    args = parser.parse_args()

    # Validate environment variables
    if not SERVER:
        print("Error: POSTGRES_SERVER environment variable is required")
        sys.exit(1)

    if args.mode in ("sync", "both"):
        run_everlasting_sync_queries(args.interval)

    if args.mode in ("async", "both"):
        if args.mode == "both":
            print("\n" + "=" * 60 + "\n")
        await run_everlasting_async_queries(args.interval)


if __name__ == "__main__":
    # Set Windows event loop policy for compatibility if needed
    if sys.platform.startswith("win"):
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    asyncio.run(main())
