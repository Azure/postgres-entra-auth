# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""
Azure PostgreSQL Entra ID Integration Library

This library provides connection classes for using Azure Entra ID authentication
with Azure Database for PostgreSQL across different PostgreSQL drivers.

Available modules (with optional dependencies):
- psycopg2: Support for psycopg2 driver (install with: pip install azurepg-entra[psycopg2])
- psycopg3: Support for psycopg (v3) driver (install with: pip install azurepg-entra[psycopg3])
- sqlalchemy: Support for SQLAlchemy ORM (install with: pip install azurepg-entra[sqlalchemy])

Core dependencies (always available):
- azure-identity: For Azure Entra ID authentication
- azure-core: Core Azure SDK functionality
"""

__version__ = "0.1.0"
__author__ = "Microsoft Corporation"
