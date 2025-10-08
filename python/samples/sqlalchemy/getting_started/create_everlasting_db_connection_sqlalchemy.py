"""
Sample demonstrating everlasting synchronous and asynchronous SQLAlchemy connections 
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
from sqlalchemy import create_engine, text
from sqlalchemy.ext.asyncio import create_async_engine

from azurepg_entra.sqlalchemy import (
    enable_entra_authentication,
    enable_entra_authentication_async,
)

# Load environment variables from .env file
load_dotenv()
SERVER = os.getenv("POSTGRES_SERVER")
DATABASE = os.getenv("POSTGRES_DATABASE", "postgres")


def run_everlasting_sync_queries(interval_minutes: int = 2) -> None:
    """Run synchronous database queries indefinitely with SQLAlchemy and Entra authentication."""
    
    print("=== Running Everlasting Synchronous SQLAlchemy Connection Example ===")
    print(f"Running queries every {interval_minutes} minutes...")
    print("Press Ctrl+C to stop\n")
    
    # Create synchronous engine with Entra authentication
    engine = create_engine(f"postgresql+psycopg://{SERVER}/{DATABASE}")
    enable_entra_authentication(engine)
    
    execution_count = 0
    
    try:
        while True:
            execution_count += 1
            current_time = datetime.now().strftime("%H:%M:%S")
            
            print(f"Sync Execution #{execution_count} at {current_time}")
            
            try:
                with engine.connect() as conn:
                    # Query 1: Get PostgreSQL version
                    result = conn.execute(text("SELECT version()"))
                    row = result.fetchone()
                    version = row[0] if row else "Unknown"
                    print(f"Connected to PostgreSQL: {version[:50]}...")
                    
                    # Query 2: Get current user
                    result = conn.execute(text("SELECT current_user"))
                    row = result.fetchone()
                    user = row[0] if row else "Unknown"
                    print(f"Connected as: {user}")
                    
                    # Query 3: Get current timestamp
                    result = conn.execute(text("SELECT now()"))
                    row = result.fetchone()
                    timestamp = row[0] if row else "Unknown"
                    print(f"Server time: {timestamp}")
                    
                    print("Sync query execution successful!")
                    
            except Exception as e:
                print(f"Database error: {e}")
            
            print(f"Waiting {interval_minutes} minutes until next execution...\n")
            time.sleep(interval_minutes * 60)
    finally:
        engine.dispose()


async def run_everlasting_async_queries(interval_minutes: int = 2) -> None:
    """Run asynchronous database queries indefinitely with SQLAlchemy and Entra authentication."""
    
    print("=== Running Everlasting Asynchronous SQLAlchemy Connection Example ===")
    print(f"Running queries every {interval_minutes} minutes...")
    print("Press Ctrl+C to stop\n")
    
    # Create asynchronous engine with Entra authentication
    engine = create_async_engine(f"postgresql+psycopg://{SERVER}/{DATABASE}")
    enable_entra_authentication_async(engine)
    
    execution_count = 0
    
    try:
        while True:
            execution_count += 1
            current_time = datetime.now().strftime("%H:%M:%S")
            
            print(f"Async Execution #{execution_count} at {current_time}")
            
            try:
                async with engine.connect() as conn:
                    # Query 1: Get PostgreSQL version
                    result = await conn.execute(text("SELECT version()"))
                    row = result.fetchone()
                    version = row[0] if row else "Unknown"
                    print(f"Connected to PostgreSQL: {version[:50]}...")
                    
                    # Query 2: Get current user
                    result = await conn.execute(text("SELECT current_user"))
                    row = result.fetchone()
                    user = row[0] if row else "Unknown"
                    print(f"Connected as: {user}")
                    
                    # Query 3: Get current timestamp
                    result = await conn.execute(text("SELECT now()"))
                    row = result.fetchone()
                    timestamp = row[0] if row else "Unknown"
                    print(f"Server time: {timestamp}")
                    
                    print("Async query execution successful!")
                    
            except Exception as e:
                print(f"Database error: {e}")
            
            print(f"Waiting {interval_minutes} minutes until next execution...\n")
            await asyncio.sleep(interval_minutes * 60)
    finally:
        await engine.dispose()


async def main() -> None:
    """Main function with command line argument parsing."""
    parser = argparse.ArgumentParser(
        description="Demonstrate everlasting SQLAlchemy connections with Azure Entra ID authentication"
    )
    parser.add_argument(
        "--mode",
        choices=["sync", "async", "both"],
        default="both",
        help="Run synchronous, asynchronous, or both examples (default: both)"
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=2,
        help="Query execution interval in minutes (default: 2)"
    )
    args = parser.parse_args()
    
    # Validate environment variables
    if not SERVER:
        print("Error: POSTGRES_SERVER environment variable is required")
        sys.exit(1)
    
    print(f"Target server: {SERVER}")
    print(f"Target database: {DATABASE}")
    print(f"Query interval: {args.interval} minutes")
    print(f"Mode: {args.mode}\n")
    
    if args.mode in ("sync", "both"):
        run_everlasting_sync_queries(args.interval)
    
    if args.mode in ("async", "both"):
        if args.mode == "both":
            print("\n" + "="*60 + "\n")
        await run_everlasting_async_queries(args.interval)


if __name__ == "__main__":
    # Set Windows event loop policy for compatibility if needed
    if sys.platform.startswith('win'):
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    
    asyncio.run(main())