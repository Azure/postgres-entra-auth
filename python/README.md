# azure-postgresql-auth: Azure Database for PostgreSQL Entra ID Authentication

This package provides seamless Azure Entra ID authentication for Python database drivers connecting to Azure Database for PostgreSQL. It supports both legacy and modern PostgreSQL drivers with automatic token management and connection pooling.

## Features

- **🔐 Azure Entra ID Authentication**: Automatic token acquisition and refresh for secure database connections
- **🔄 Multi-Driver Support**: Works with psycopg2, psycopg3, and SQLAlchemy
- **⚡ Connection Pooling**: Built-in support for both synchronous and asynchronous connection pools
- **🏗️ Clean Architecture**: Simple package structure with `azure_postgresql_auth.psycopg2`, `azure_postgresql_auth.psycopg3`, and `azure_postgresql_auth.sqlalchemy`
- **🔄 Automatic Token Management**: Handles token acquisition, validation, and refresh automatically
- **🌐 Cross-platform**: Works on Windows, Linux, and macOS
- **📦 Flexible Installation**: Optional dependencies for different driver combinations

## Installation

### Basic Installation

Install the core package (includes Azure Identity dependencies only):
```bash
pip install azure-postgresql-auth
```

### Driver-Specific Installation

Choose the installation option based on which PostgreSQL drivers you need:

```bash
# For psycopg3 (modern psycopg, recommended for new projects)
pip install "azure-postgresql-auth[psycopg3]"

# For psycopg2 (legacy support)
pip install "azure-postgresql-auth[psycopg2]"

# For SQLAlchemy with psycopg3 backend
pip install "azure-postgresql-auth[sqlalchemy]"

# All database drivers combined
pip install "azure-postgresql-auth[drivers]"

# Everything including development tools
pip install "azure-postgresql-auth[all]"
```

### Development Installation

Install from source for development:
```bash
git clone https://github.com/v-anarendra_microsoft/entra-id-integration-for-drivers.git
cd entra-id-integration-for-drivers/python

# Install with all dependencies for development
pip install -e ".[dev]"

# Or install specific driver combinations
pip install -e ".[psycopg3,dev]"
```

## Configuration

### Environment Variables

The samples use environment variables to configure database connections.

Copy `.env.example` into a `.env` file in the same directory and update the variables.
```env
POSTGRES_SERVER=<your-server.postgres.database.azure.com>
POSTGRES_DATABASE=<your_database_name>
```

## Quick Start

### Running the Samples

The repository includes comprehensive working examples in the `samples/` directory:

- **`samples/psycopg2/getting_started/`**: psycopg2 (legacy driver support)
- **`samples/psycopg3/getting_started/`**: psycopg3 examples (modern driver, recommended)
- **`samples/sqlalchemy/getting_started/`**: SQLAlchemy examples with psycopg3 backend

Configure your environment variables first, then run the samples:

```bash
# Copy and configure environment
cp samples/psycopg3/getting_started/.env.example samples/psycopg3/getting_started/.env
# Edit .env with your Azure PostgreSQL server details

# Test psycopg2 (legacy driver)
python samples/psycopg2/getting_started/create_db_connection.py --mode both

# Test psycopg3 (modern driver, recommended)
python samples/psycopg3/getting_started/create_db_connection.py --mode both

# Test SQLAlchemy 
python samples/sqlalchemy/getting_started/create_db_connection.py --mode both
```

## Usage

Choose the driver that best fits your project needs:

- **psycopg3**: Modern PostgreSQL driver (recommended for new projects)
- **psycopg2**: Legacy PostgreSQL driver (for existing projects)  
- **SQLAlchemy**: High-level ORM/Core interface

---

## psycopg2 Driver (Legacy Support)

> **Note**: psycopg2 is in maintenance mode. For new projects, consider using psycopg3 instead.

The psycopg2 integration provides synchronous connection support with Azure Entra ID authentication through connection pooling.

### Installation
```bash
pip install "azure-postgresql-auth[psycopg2]"
```

### Connection Pooling (Recommended)

```python
from azure_postgresql_auth.psycopg2 import EntraConnection # import library
from psycopg2 import pool # import to use pooling

with pool.ThreadedConnectionPool(
    minconn=1,
    maxconn=5,
    host="your-server.postgres.database.azure.com",
    database="your_database",
    connection_factory=EntraConnection
) as connection_pool:
```

### Direct Connection

```python
from azure_postgresql_auth.psycopg2 import EntraConnection # import library

with EntraConnection(
    "postgresql://your-server.postgres.database.azure.com:5432/your_database"
) as conn
```

---

## psycopg3 Driver (Recommended)

psycopg3 is the modern, actively developed PostgreSQL driver with native async support and better performance.

### Installation
```bash
pip install "azure-postgresql-auth[psycopg3]"
```

### Synchronous Connection

```python
from azure_postgresql_auth.psycopg3 import EntraConnection # import library
from psycopg_pool import ConnectionPool # import to use pooling

with ConnectionPool(
    conninfo="postgresql://your-server.postgres.database.azure.com:5432/your_database",
    connection_class=EntraConnection,
    min_size=1,   # keep at least 1 connection always open
    max_size=5,   # allow up to 5 concurrent connections
) as pool
```

### Asynchronous Connection

```python
from azure_postgresql_auth.psycopg3 import AsyncEntraConnection # import library
from psycopg_pool import AsyncConnectionPool # import to use pooling 

async with AsyncConnectionPool(
    conninfo="postgresql://your-server.postgres.database.azure.com:5432/your_database",
    connection_class=AsyncEntraConnection,
    min_size=1,   # keep at least 1 connection always open
    max_size=5,   # allow up to 5 concurrent connections
) as pool
```

---

## SQLAlchemy Integration

SQLAlchemy integration uses psycopg3 as the backend driver with automatic Entra ID authentication through event listeners.

> **For more information**: See SQLAlchemy's documentation on [controlling how parameters are passed to the DBAPI connect function](https://docs.sqlalchemy.org/en/20/core/engines.html#controlling-how-parameters-are-passed-to-the-dbapi-connect-function).

### Installation
```bash
pip install "azure-postgresql-auth[sqlalchemy]"
```

### Synchronous Engine

```python
from sqlalchemy import create_engine
from azure_postgresql_auth.sqlalchemy import enable_entra_authentication # import library

with create_engine("postgresql+psycopg://your-server.postgres.database.azure.com/your_database") as engine:
    # Enable Entra ID authentication
    enable_entra_authentication(engine)
    
    # Core usage
    with engine.connect() as conn:

    # ORM usage
    from sqlalchemy.orm import sessionmaker
    Session = sessionmaker(bind=engine)
```

### Asynchronous Engine

```python
from sqlalchemy.ext.asyncio import create_async_engine
from azure_postgresql_auth.sqlalchemy import enable_entra_authentication_async # import library

async with create_async_engine("postgresql+psycopg://your-server.postgres.database.azure.com/your_database") as engine:
    # Enable Entra ID authentication for async
    enable_entra_authentication_async(engine)
    
    # Async Core usage
    async with engine.connect() as conn:
    
    # Async ORM usage
    from sqlalchemy.ext.asyncio import async_sessionmaker
    AsyncSession = async_sessionmaker(engine, expire_on_commit=False)
```

## How It Works

### Authentication Flow

1. **Token Acquisition**: Uses Azure Identity libraries (`DefaultAzureCredential` by default) to acquire access tokens from Azure Entra ID
2. **Automatic Refresh**: Tokens are automatically refreshed before each new database connection  
3. **Secure Transport**: Tokens are passed as passwords in PostgreSQL connection strings over SSL
4. **Server Validation**: Azure Database for PostgreSQL validates the token and establishes the authenticated connection
5. **User Mapping**: The token's user principal name (UPN) is mapped to a PostgreSQL user for authorization

### Token Scopes

The package automatically requests the correct OAuth2 scopes:
- **Database scope**: `https://ossrdbms-aad.database.windows.net/.default` (primary)
- **Management scope**: `https://management.azure.com/.default` (fallback for managed identities)

### Security Features

- **🔒 Token-based authentication**: No passwords stored or transmitted
- **⏰ Automatic expiration**: Tokens expire and are refreshed automatically
- **🛡️ SSL enforcement**: All connections require SSL encryption
- **🔑 Principle of least privilege**: Only database-specific scopes are requested
---

## Troubleshooting

### Common Issues

**Authentication Errors**
```bash
# Error: "password authentication failed"
# Solution: Ensure your Azure identity has been granted access to the database
# Run this SQL as a database administrator:
CREATE ROLE "your-user@your-domain.com" WITH LOGIN;
GRANT ALL PRIVILEGES ON DATABASE your_database TO "your-user@your-domain.com";
```

**Connection Timeouts**
```python
# Increase connection timeout for slow networks
conn = SyncEntraConnection.connect(
    "postgresql://server:5432/db", 
    connect_timeout=30  # 30 seconds instead of default 10
)
```

**Windows Async Issues**
```python
# Fix Windows event loop compatibility
import asyncio
import sys

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
```

### Debug Logging

Enable debug logging to troubleshoot authentication issues:

```python
import logging
logging.basicConfig(level=logging.DEBUG)

# This will show token acquisition and connection details
conn = SyncEntraConnection.connect("postgresql://server:5432/db")
```

---

## Contributing

We welcome contributions! Please see [CONTRIBUTING.md](../CONTRIBUTING.md) for guidelines.


---

## License

This project is licensed under the MIT License - see the [LICENSE](../LICENSE) file for details.
