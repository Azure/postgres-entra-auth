# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""
SQLAlchemy integration for Azure PostgreSQL with Entra ID authentication.

This module provides integration between SQLAlchemy and Azure Entra ID
authentication for PostgreSQL connections. It automatically handles token acquisition
and credential injection through SQLAlchemy's event system.

Requirements:
    Install with: pip install azurepg-entra[sqlalchemy]

    This will install:
    - sqlalchemy>=2.0.0
    - aiohttp>=3.8.0

Functions:
    enable_entra_authentication: Enable Entra ID authentication for synchronous SQLAlchemy engines
    enable_entra_authentication_async: Enable Entra ID authentication for asynchronous SQLAlchemy engines
"""

from .async_entra_connection import enable_entra_authentication_async
from .entra_connection import enable_entra_authentication

__all__ = [
    "enable_entra_authentication",
    "enable_entra_authentication_async",
]
