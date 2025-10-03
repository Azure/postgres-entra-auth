# Copyright (c) Microsoft. All rights reserved.
"""
SQLAlchemy integration for Azure PostgreSQL with Entra ID authentication.
"""

from .sqlalchemy_entra_id_extension import (
    create_engine_with_entra,
    create_async_engine_with_entra,
)

__all__ = [
    "create_engine_with_entra",
    "create_async_engine_with_entra",
]