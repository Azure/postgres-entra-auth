# Copyright (c) Microsoft. All rights reserved.
"""
Psycopg2 + aiopg support for Azure Entra ID authentication with Azure Database for PostgreSQL.

This module provides connection functions that handle Azure Entra ID token acquisition
and authentication for both synchronous (psycopg2) and asynchronous (aiopg) PostgreSQL connections.

Requirements:
    Install with: pip install azurepg-entra[psycopg2]
    
    This will install:
    - psycopg2-binary>=2.8.0
    - aiopg>=1.3.0 (for async support)

Functions:
    connect_with_entra: Synchronous connection function with Entra ID authentication (psycopg2)
    connect_with_entra_async: Asynchronous connection function with Entra ID authentication (aiopg)
    get_entra_conninfo: Synchronous function to get Entra authentication info
    get_entra_conninfo_async: Asynchronous function to get Entra authentication info

Example usage:
    # Synchronous connection
    from azurepg_entra.psycopg2 import connect_with_entra
    
    conn = connect_with_entra(
        host="myserver.postgres.database.azure.com",
        dbname="mydatabase",
        port=5432
    )
    
    # Asynchronous connection
    from azurepg_entra.psycopg2 import connect_with_entra_async
    
    conn = await connect_with_entra_async(
        host="myserver.postgres.database.azure.com", 
        dbname="mydatabase",
        port=5432
    )
"""

try:
    from .psycopg2_entra_id_extension import (
        connect_with_entra,
        connect_with_entra_async
    )
    
    __all__ = [
        "connect_with_entra",
        "connect_with_entra_async"
    ]
    
except ImportError as e:
    # Provide a helpful error message if psycopg2/aiopg dependencies are missing
    raise ImportError(
        "psycopg2 dependencies are not installed. "
        "Install them with: pip install azurepg-entra[psycopg2]"
    ) from e