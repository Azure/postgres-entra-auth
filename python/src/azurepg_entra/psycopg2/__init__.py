# Copyright (c) Microsoft. All rights reserved.

"""
Psycopg2 support for Azure Entra ID authentication with Azure Database for PostgreSQL.

This module provides a connection class that handles Azure Entra ID token acquisition
and authentication for synchronous PostgreSQL connections.

Requirements:
    Install with: pip install azurepg-entra[psycopg2]

    This will install:
    - psycopg2-binary>=2.9.0

Classes:
    EntraConnection: Synchronous connection class with Entra ID authentication
"""

from .entra_connection import (
    EntraConnection,
)

__all__ = [
    "EntraConnection",
]
