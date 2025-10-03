# Copyright (c) Microsoft. All rights reserved.
import psycopg
import logging
from typing import Optional, Any, TYPE_CHECKING
from urllib.parse import urlparse, urlunparse
from azurepg_entra.core import get_entra_conninfo, get_entra_conninfo_async
from azure.core.credentials import TokenCredential
from azure.core.credentials_async import AsyncTokenCredential
from azure.identity import DefaultAzureCredential as DefaultAzureCredential
from azure.identity.aio import DefaultAzureCredential as AsyncDefaultAzureCredential
from sqlalchemy.engine.interfaces import DBAPIConnection
from sqlalchemy.ext.asyncio.engine import AsyncEngine

try:
    from sqlalchemy import create_engine, Engine
except ImportError:
    raise ImportError("sqlalchemy is required. Install with: pip install sqlalchemy")

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import create_async_engine
else:
    try:
        from sqlalchemy.ext.asyncio import create_async_engine
    except ImportError:
        create_async_engine = None

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def create_engine_with_entra(
    url: str,
    credential: Optional[TokenCredential] = None,
    **kwargs: Any
) -> Engine:
    """Creates a SQLAlchemy Engine using Entra authentication for Azure PostgreSQL.

    This function handles Azure Entra ID token acquisition and creates a SQLAlchemy engine
    that automatically refreshes tokens for each new connection. This solves the token 
    expiration issue by acquiring fresh tokens on each connection attempt.

    Parameters:
        url (str): The database URL. Username and password will be replaced with Entra credentials.
        credential (TokenCredential, optional): The credential used for token acquisition.
            If None, the default Azure credentials are used.
        **kwargs: Additional engine creation parameters passed to create_engine()

    Returns:
        Engine: A SQLAlchemy engine configured with Entra authentication and automatic token refresh.

    Raises:
        ValueError: If the provided credential is not a valid TokenCredential.

    Example:
        engine = create_engine_with_entra(
            "postgresql+psycopg://myserver.postgres.database.azure.com/mydatabase"
        )
    """
    credential = credential or DefaultAzureCredential()
    if credential and not isinstance(credential, TokenCredential):
        raise ValueError("credential must be a TokenCredential for synchronous engines")
    
    # Parse the original URL to extract connection parameters
    parsed = urlparse(url)
    
    def connect_with_fresh_token() -> DBAPIConnection | None:
        """Custom connection factory that gets a fresh token each time."""
        logger.info("Creating new connection with fresh Entra token")
        
        # Get fresh Entra authentication info for each connection
        entra_conninfo = get_entra_conninfo(credential)
        
        # Build authenticated URL with fresh token
        parsed_copy = parsed._replace(
            netloc=f"{entra_conninfo['user']}:{entra_conninfo['password']}@{parsed.hostname}" + 
                   (f":{parsed.port}" if parsed.port else "")
        )
        auth_url = urlunparse(parsed_copy)
        
        # Create a temporary engine with the authenticated URL and get the DBAPI connection
        temp_engine = create_engine(auth_url)
        raw_conn = temp_engine.raw_connection()
        # Return the underlying DBAPI connection, not the SQLAlchemy wrapper
        return raw_conn.dbapi_connection
    
    # Create base URL without credentials for the engine
    base_url = f"{parsed.scheme or 'postgresql'}://{parsed.hostname}"
    if parsed.port:
        base_url += f":{parsed.port}"
    if parsed.path:
        base_url += parsed.path
    if parsed.query:
        base_url += f"?{parsed.query}"
    
    # Create engine with custom connection factory
    return create_engine(base_url, creator=connect_with_fresh_token, **kwargs)

def create_async_engine_with_entra(
    url: str,
    credential: Optional[AsyncTokenCredential] = None,
    **kwargs: Any
) -> AsyncEngine:
    """Creates an async SQLAlchemy Engine using Entra authentication for Azure PostgreSQL.

    This function handles Azure Entra ID token acquisition and creates an async SQLAlchemy engine
    that automatically refreshes tokens for each new connection. This solves the token 
    expiration issue by acquiring fresh tokens on each connection attempt.

    Parameters:
        url (str): The database URL. Username and password will be replaced with Entra credentials.
        credential (AsyncTokenCredential, optional): The async credential used for token acquisition.
            If None, the default Azure credentials are used.
        **kwargs: Additional engine creation parameters passed to create_async_engine()

    Returns:
        AsyncEngine: An async SQLAlchemy engine configured with Entra authentication and automatic token refresh.

    Raises:
        ImportError: If sqlalchemy.ext.asyncio is not available.
        ValueError: If the provided credential is not a valid AsyncTokenCredential.

    Example:
        engine = await create_async_engine_with_entra(
            "postgresql+psycopg://myserver.postgres.database.azure.com/mydatabase"
        )
    """
    if create_async_engine is None:
        raise ImportError(
            "sqlalchemy.ext.asyncio is required for async engines. "
            "Install with: pip install sqlalchemy[asyncio]"
        )
    
    credential = credential or AsyncDefaultAzureCredential()
    if credential and not isinstance(credential, AsyncTokenCredential):
        raise ValueError("credential must be an AsyncTokenCredential for async engines")
    
    # Parse the original URL to extract connection parameters
    parsed = urlparse(url)
    
    async def async_connect_with_fresh_token() -> psycopg.AsyncConnection:
        """Custom async connection factory that gets a fresh token each time."""
        logger.info("Creating new async connection with fresh Entra token")
        
        # Get fresh Entra authentication info for each connection
        entra_conninfo = await get_entra_conninfo_async(credential)
        
        # For async, we need to return the raw async connection directly
        # Import the appropriate async driver and create connection directly
        if parsed.scheme == 'postgresql+psycopg' or parsed.scheme == 'postgresql':
            return await psycopg.AsyncConnection.connect(
                host=parsed.hostname,
                port=parsed.port or 5432,
                dbname=parsed.path.lstrip('/') if parsed.path else 'postgres',
                user=entra_conninfo['user'],
                password=entra_conninfo['password']
            )
        else:
            raise ValueError(f"Unsupported async URL scheme: {parsed.scheme}. Use postgresql+psycopg or postgresql")
    
    # Create base URL without credentials for the engine
    base_url = f"{parsed.scheme}://{parsed.hostname}"
    if parsed.port:
        base_url += f":{parsed.port}"
    if parsed.path:
        base_url += parsed.path
    if parsed.query:
        base_url += f"?{parsed.query}"
    
    # Create async engine with custom connection factory
    return create_async_engine(base_url, async_creator=async_connect_with_fresh_token, **kwargs)
