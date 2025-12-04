# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""
Psycopg3 support for Azure Entra ID authentication with Azure Database for PostgreSQL.

This module provides connection classes that extend psycopg's Connection and AsyncConnection
to automatically handle Azure Entra ID token acquisition and authentication.

Requirements:
    Install with: pip install azurepg-entra[psycopg3]

    This will install:
    - psycopg[binary]>=3.1.0
    - aiohttp>=3.8.0

Classes:
    EntraConnection: Synchronous connection class with Entra ID authentication
    AsyncEntraConnection: Asynchronous connection class with Entra ID authentication
"""

from .async_entra_connection import AsyncEntraConnection
from .entra_connection import EntraConnection

__all__ = ["EntraConnection", "AsyncEntraConnection"]
