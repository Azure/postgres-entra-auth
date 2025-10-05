# Copyright (c) Microsoft. All rights reserved.
"""
Psycopg2 support for Azure Entra ID authentication with Azure Database for PostgreSQL.

This module provides connection classes that handle Azure Entra ID token acquisition
and authentication for synchronous (psycopg2) PostgreSQL connections.

Requirements:
    Install with: pip install azurepg-entra[psycopg2]
    
    This will install:
    - psycopg2-binary>=2.8.0

Classes:
    SyncEntraConnection: Synchronous connection class with Entra ID authentication (psycopg2)

Example usage:
    # Synchronous connection
    from azurepg_entra.psycopg2 import SyncEntraConnection
    
    connection_pool = pool.ThreadedConnectionPool(
        minconn=1,
        maxconn=5,
        host=SERVER,
        database=DATABASE,
        connection_factory=SyncEntraConnection
    )
"""

try:
    from .psycopg2_entra_id_extension import (
        SyncEntraConnection,
    )
    
    __all__ = [
        "SyncEntraConnection",
    ]
    
except ImportError as e:
    # Provide a helpful error message if psycopg2 dependencies are missing
    raise ImportError(
        "psycopg2 dependencies are not installed. "
        "Install them with: pip install azurepg-entra[psycopg2]"
    ) from e