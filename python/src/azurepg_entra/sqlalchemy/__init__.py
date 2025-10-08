# Copyright (c) Microsoft. All rights reserved.
"""
SQLAlchemy integration for Azure PostgreSQL with Entra ID authentication.

This module provides integration between SQLAlchemy and Azure Entra ID
authentication for PostgreSQL connections. It automatically handles token acquisition
and credential injection through SQLAlchemy's event system.

Usage:
    Synchronous engines:
        from sqlalchemy import create_engine
        from azurepg_entra.sqlalchemy import enable_entra_authentication

        engine = create_engine("postgresql://myserver.postgres.database.azure.com/mydb")
        enable_entra_authentication(engine)

    Asynchronous engines:
        from sqlalchemy.ext.asyncio import create_async_engine
        from azurepg_entra.sqlalchemy import enable_entra_authentication_async

        engine = create_async_engine("postgresql+asyncpg://myserver.postgres.database.azure.com/mydb")
        enable_entra_authentication_async(engine)

Functions:
    enable_entra_authentication: Enable Entra ID auth for synchronous SQLAlchemy engines
    enable_entra_authentication_async: Enable Entra ID auth for asynchronous SQLAlchemy engines
"""

from .async_entra_connection import enable_entra_authentication_async
from .entra_connection import enable_entra_authentication

__all__ = [
    "enable_entra_authentication",
    "enable_entra_authentication_async",
]
