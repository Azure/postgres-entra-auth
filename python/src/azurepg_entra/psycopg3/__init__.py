# Copyright (c) Microsoft. All rights reserved.
"""
Psycopg3 (psycopg) support for Azure Entra ID authentication with Azure Database for PostgreSQL.

This module provides connection classes that extend psycopg's Connection and AsyncConnection
to automatically handle Azure Entra ID token acquisition and authentication.

Requirements:
    Install with: pip install azurepg-entra[psycopg3]

    This will install:
    - psycopg[binary]>=3.1.0

Classes:
    EntraConnection: Synchronous connection class with Entra ID authentication
    AsyncEntraConnection: Asynchronous connection class with Entra ID authentication

Example usage:
    from azurepg_entra.psycopg3 import EntraConnection, AsyncEntraConnection
    from psycopg_pool import ConnectionPool, AsyncConnectionPool

    # Synchronous usage
    pool = ConnectionPool(
        conninfo="postgresql://myserver:5432/mydb",
        connection_class=EntraConnection
    )

    # Asynchronous usage
    async_pool = AsyncConnectionPool(
        conninfo="postgresql://myserver:5432/mydb",
        connection_class=AsyncEntraConnection
    )
"""

try:
    from .async_entra_connection import AsyncEntraConnection
    from .entra_connection import EntraConnection

    __all__ = ["EntraConnection", "AsyncEntraConnection"]
except ImportError as e:
    # Provide a helpful error message if psycopg dependencies are missing
    raise ImportError(
        "psycopg3 dependencies are not installed. "
        "Install them with: pip install azurepg-entra[psycopg3]"
    ) from e
