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
    EntraConnection: Synchronous connection class with Entra ID authentication (psycopg2)

Example usage:
    # Synchronous connection
    from azurepg_entra.psycopg2 import EntraConnection

    connection_pool = pool.ThreadedConnectionPool(
        minconn=1,
        maxconn=5,
        host=SERVER,
        database=DATABASE,
        connection_factory=EntraConnection
    )
"""

from .entra_connection import (
    EntraConnection,
)

__all__ = [
    "EntraConnection",
]
