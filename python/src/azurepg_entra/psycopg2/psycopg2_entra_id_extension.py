# Copyright (c) Microsoft. All rights reserved.
"""
Connection classes for using Entra auth with Azure DB for PostgreSQL (psycopg2 + aiopg version).
This module provides both synchronous and asynchronous connection classes that allow you to connect to Azure DB for PostgreSQL
using Entra authentication. Uses psycopg2 for sync connections and aiopg for async connections.

Sync Example (psycopg2):
    from azurepg_entra.psycopg2 import connect_with_entra
    
    conn = connect_with_entra(host="myserver.postgres.database.azure.com", dbname="mydatabase")

Async Example (aiopg):
    from azurepg_entra.psycopg2 import connect_with_entra_async
    
    conn = await connect_with_entra_async(host="myserver.postgres.database.azure.com", dbname="mydatabase")

Note: Async functionality requires aiopg: pip install aiopg
"""

from typing import Any, Optional, TYPE_CHECKING, cast

import psycopg2

from azurepg_entra.core import get_entra_conninfo, get_entra_conninfo_async

if TYPE_CHECKING:
    import aiopg
else:
    try:
        import aiopg
    except ImportError:
        aiopg = None

from azure.core.credentials import TokenCredential
from azure.core.credentials_async import AsyncTokenCredential
from azure.identity import DefaultAzureCredential as DefaultAzureCredential
from azure.identity.aio import DefaultAzureCredential as AsyncDefaultAzureCredential

AZURE_DB_FOR_POSTGRES_SCOPE = "https://ossrdbms-aad.database.windows.net/.default"
AZURE_MANAGEMENT_SCOPE = "https://management.azure.com/.default"

def connect_with_entra(credential: Optional[TokenCredential] = None, **kwargs: Any) -> psycopg2.extensions.connection:
    """Creates a synchronous PostgreSQL connection using Entra authentication.

    This function handles Azure Entra ID token acquisition and creates a psycopg2 connection
    with the appropriate user and password parameters.

    Parameters:
        credential (TokenCredential, optional): The credential used for token acquisition.
            If None, the default Azure credentials are used.
        **kwargs: Additional connection parameters (host, port, dbname, etc.)

    Returns:
        psycopg2.extensions.connection: An open synchronous connection to PostgreSQL.

    Raises:
        ValueError: If the provided credential is not a valid TokenCredential.
    """
    credential = credential or DefaultAzureCredential()
    if credential and not isinstance(credential, TokenCredential):
        raise ValueError("credential must be a TokenCredential for synchronous connections")
    
    # Check if we need to acquire Entra authentication info
    if not kwargs.get("user") or not kwargs.get("password"):
        entra_conninfo = get_entra_conninfo(credential)
        # Always use the token password when Entra authentication is needed
        kwargs["password"] = entra_conninfo["password"]
        if not kwargs.get("user"):
            # If user isn't already set, use the username from the token
            kwargs["user"] = entra_conninfo["user"]

    return cast(psycopg2.extensions.connection, psycopg2.connect(**kwargs))

async def connect_with_entra_async(credential: Optional[AsyncTokenCredential] = None, **kwargs: Any) -> aiopg.Connection:
    """Creates an asynchronous PostgreSQL connection using Entra authentication.

    This function handles Azure Entra ID token acquisition and creates an aiopg connection
    with the appropriate user and password parameters.

    Parameters:
        credential (AsyncTokenCredential, optional): The async credential used for token acquisition.
            If None, the default Azure credentials are used.
        **kwargs: Additional connection parameters (host, port, dbname, etc.)

    Returns:
        aiopg connection: An open asynchronous connection to PostgreSQL.

    Raises:
        ImportError: If aiopg is not installed.
        ValueError: If the provided credential is not a valid AsyncTokenCredential.
    """
    if aiopg is None:
        raise ImportError(
            "aiopg is required for async connections. Install with: pip install aiopg"
        )
    
    credential = credential or AsyncDefaultAzureCredential()    
    if credential and not isinstance(credential, AsyncTokenCredential):
        raise ValueError("credential must be an AsyncTokenCredential for async connections")
    
    # Check if we need to acquire Entra authentication info
    if not kwargs.get("user") or not kwargs.get("password"):
        entra_conninfo = await get_entra_conninfo_async(credential)
        # Always use the token password when Entra authentication is needed
        kwargs["password"] = entra_conninfo["password"]
        if not kwargs.get("user"):
            # If user isn't already set, use the username from the token
            kwargs["user"] = entra_conninfo["user"]
    
    return await aiopg.connect(**kwargs)