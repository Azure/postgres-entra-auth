# Copyright (c) Microsoft. All rights reserved.
import asyncio
import logging
import sys
from sqlalchemy import Engine, event
from sqlalchemy.ext.asyncio import AsyncEngine
from typing import Optional
from azure.core.credentials import TokenCredential
from azurepg_entra.core import get_entra_conninfo, get_entra_conninfo_async

logger = logging.getLogger(__name__)

def enable_entra_authentication(engine: Engine, credential: Optional[TokenCredential] = None):
    """
    Enable Azure Entra ID authentication for a SQLAlchemy engine.
    
    This function registers an event listener that automatically provides
    Entra ID credentials for each database connection if they are not already set.
    
    Args:
        engine: The SQLAlchemy Engine to enable Entra authentication for
        credential: Optional Azure credential. If None, uses DefaultAzureCredential
    """
    
    @event.listens_for(engine, "do_connect")
    def provide_token(dialect, conn_rec, cargs, cparams):
        """Event handler that provides Entra credentials for each connection."""
        try:
            # Check if credentials are already present
            has_user = "user" in cparams
            has_password = "password" in cparams
            
            # Only get Entra credentials if user or password is missing
            if not has_user or not has_password:
                entra_creds = get_entra_conninfo(credential)
                
                # Only update missing credentials
                if not has_user and "user" in entra_creds:
                    cparams["user"] = entra_creds["user"]
                if not has_password and "password" in entra_creds:
                    cparams["password"] = entra_creds["password"]
                    
                logger.debug(f"Provided Entra credentials for user: {entra_creds.get('user', 'unknown')}")
            else:
                logger.debug("User and password already present, skipping Entra authentication")
        except Exception as e:
            logger.error(f"Failed to get Entra credentials: {e}")
            raise


def enable_entra_authentication_async(engine: AsyncEngine, credential: Optional[TokenCredential] = None):
    """
    Enable Azure Entra ID authentication for an async SQLAlchemy engine.

    This function registers an event listener that automatically provides
    Entra ID credentials for each database connection if they are not already set.
    
    Args:
        engine: The async SQLAlchemy Engine to enable Entra authentication for
        credential: Optional Azure credential. If None, uses DefaultAzureCredential
    """

    @event.listens_for(engine.sync_engine, "do_connect")
    def provide_token_async(dialect, conn_rec, cargs, cparams):
        """Event handler that provides Entra credentials for each async connection."""
        try:
            # Check if credentials are already present
            has_user = "user" in cparams
            has_password = "password" in cparams
            
            # Only get Entra credentials if user or password is missing
            if not has_user or not has_password:
                # For async engines, we need to handle the async credential fetching
                try:
                    # Try to get the current event loop
                    asyncio.get_running_loop()
                    # If we're in a running loop, we need to run the async function in a thread
                    import concurrent.futures
                    with concurrent.futures.ThreadPoolExecutor() as executor:
                        future = executor.submit(asyncio.run, get_entra_conninfo_async(credential))
                        entra_creds = future.result()
                except RuntimeError:
                    # No running event loop, we can use asyncio.run directly
                    # Set Windows event loop policy for compatibility if needed
                    if sys.platform.startswith('win'):
                        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
                    entra_creds = asyncio.run(get_entra_conninfo_async(credential))
                
                logger.debug("Successfully obtained async Entra credentials")
                
                # Only update missing credentials
                if not has_user and "user" in entra_creds:
                    cparams["user"] = entra_creds["user"]
                if not has_password and "password" in entra_creds:
                    cparams["password"] = entra_creds["password"]
                    
                logger.debug(f"Provided async Entra credentials for user: {entra_creds.get('user', 'unknown')}")
            else:
                logger.debug("User and password already present, skipping Entra authentication")
        except Exception as e:
            logger.error(f"Failed to get async Entra credentials: {e}")
            raise