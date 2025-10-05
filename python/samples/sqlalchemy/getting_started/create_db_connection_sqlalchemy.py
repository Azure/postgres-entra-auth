"""
Sample demonstrating both synchronous and asynchronous SQLAlchemy connections 
with Azure Entra ID authentication for Azure PostgreSQL.
"""

from sqlalchemy import create_engine, text
from sqlalchemy.ext.asyncio import create_async_engine
from azurepg_entra.sqlalchemy import enable_entra_authentication, enable_entra_authentication_async
from dotenv import load_dotenv
import argparse
import asyncio
import sys
import os

# Load environment variables from .env file
load_dotenv()
SERVER = os.getenv("POSTGRES_SERVER")
DATABASE = os.getenv("POSTGRES_DATABASE", "postgres")

def main_sync():
    """Synchronous connection example using SQLAlchemy with Entra ID authentication."""

    try:
        # Create a synchronous engine
        engine = create_engine(f"postgresql+psycopg://{SERVER}/{DATABASE}")
        
        # We add an event listener to the engine to enable Entra authentication for the
        # PostgreSQL database by acquiring an Azure access token, extracting a username from the token, and using
        # the token itself (with the PostgreSQL scope) as the password. This event listener is triggered
        # whenever we get a NEW connection from the pool backing the engine.
        enable_entra_authentication(engine)

        with engine.connect() as conn:
            # Query 1
            result = conn.execute(text("SELECT now()"))
            print(f"Sync - Database time: {result.fetchone()[0]}")
            
            # Query 2
            result = conn.execute(text("SELECT current_user"))
            print(f"Sync - Connected as: {result.fetchone()[0]}")
            
        # Clean up the engine
        engine.dispose()
    except Exception as e:
        print(f"Sync - Error connecting to database: {e}")
        raise

async def main_async():
    """Asynchronous connection example using SQLAlchemy with Entra ID authentication."""

    try:
        # Create an asynchronous engine
        engine = create_async_engine(f"postgresql+psycopg://{SERVER}/{DATABASE}")
        
        # We add an event listener to the engine to enable Entra authentication for the
        # PostgreSQL database by acquiring an Azure access token, extracting a username from the token, and using
        # the token itself (with the PostgreSQL scope) as the password. This event listener is triggered
        # whenever we get a NEW connection from the pool backing the engine.
        enable_entra_authentication_async(engine)

        async with engine.connect() as conn:
            # Query 1
            result = await conn.execute(text("SELECT now()"))
            print(f"Async - Database time: {result.fetchone()[0]}")

            # Query 2
            result = await conn.execute(text("SELECT current_user"))
            print(f"Async - Connected as: {result.fetchone()[0]}")
            
        # Clean up the engine
        await engine.dispose()
    except Exception as e:
        print(f"Async - Error connecting to database: {e}")
        raise

async def main(mode: str = "async"):
    """Main function that runs sync and/or async examples based on mode.
    
    Args:
        mode: "sync", "async", or "both" to determine which examples to run
    """
    if mode in ("sync", "both"):
        print("=== Running Synchronous SQLAlchemy Example ===")
        try:
            main_sync()
            print("✅ Sync example completed successfully!")
        except Exception as e:
            print(f"❌ Sync example failed: {e}")
    
    if mode in ("async", "both"):
        if mode == "both":
            print("\n=== Running Asynchronous SQLAlchemy Example ===")
        else:
            print("=== Running Asynchronous SQLAlchemy Example ===")
        try:
            await main_async()
            print("✅ Async example completed successfully!")
        except Exception as e:
            print(f"❌ Async example failed: {e}")

if __name__ == "__main__":
    # Parse command line arguments
    parser = argparse.ArgumentParser(
        description="Demonstrate SQLAlchemy connections with Azure Entra ID authentication"
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