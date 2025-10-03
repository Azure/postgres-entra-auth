# azurepg-entra: Azure Database for PostgreSQL Entra ID Authentication

This package provides seamless Azure Entra ID authentication for Python database drivers connecting to Azure Database for PostgreSQL. It supports both legacy and modern PostgreSQL drivers with automatic token management and connection pooling.

## Features

- **🔐 Azure Entra ID Authentication**: Automatic token acquisition and refresh for secure database connections
- **🔄 Multi-Driver Support**: Works with psycopg2, psycopg3, aiopg, asyncpg, and SQLAlchemy
- **⚡ Connection Pooling**: Built-in support for both synchronous and asynchronous connection pools
- **🏗️ Clean Architecture**: Simple package structure with `azurepg_entra.psycopg2`, `azurepg_entra.psycopg3`, and `azurepg_entra.sqlalchemy`
- **🔄 Automatic Token Management**: Handles token acquisition, validation, and refresh automatically
- **🌐 Cross-platform**: Works on Windows, Linux, and macOS
- **📦 Flexible Installation**: Optional dependencies for different driver combinations

## Installation

### Basic Installation

Install the core package (includes Azure Identity dependencies only):
```bash
pip install azurepg-entra
```

### Driver-Specific Installation

Choose the installation option based on which PostgreSQL drivers you need:

```bash
# For psycopg3 (modern psycopg, recommended for new projects)
pip install "azurepg-entra[psycopg3]"

# For psycopg2 + aiopg (legacy support)
pip install "azurepg-entra[psycopg2]"

# For SQLAlchemy with psycopg3 backend
pip install "azurepg-entra[sqlalchemy]"

# All database drivers combined
pip install "azurepg-entra[drivers]"

# Everything including development tools
pip install "azurepg-entra[all]"
```

### Development Installation

Install from source for development:
```bash
git clone https://github.com/v-anarendra_microsoft/entra-id-integration-for-drivers.git
cd entra-id-integration-for-drivers/python

# Install with all dependencies for development
pip install -e ".[all]"

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

- **`samples/psycopg2/getting_started/`**: psycopg2 + aiopg examples (legacy driver support)
- **`samples/psycopg3/getting_started/`**: psycopg3 examples (modern driver, recommended)
- **`samples/sqlalchemy/getting_started/`**: SQLAlchemy examples with psycopg3 backend

Configure your environment variables first, then run the samples:

```bash
# Copy and configure environment
cp samples/psycopg3/getting_started/.env.example samples/psycopg3/getting_started/.env
# Edit .env with your Azure PostgreSQL server details

# Test psycopg2 (legacy driver)
python samples/psycopg2/getting_started/create_db_connection_psycopg2.py --mode both

# Test psycopg3 (modern driver, recommended)
python samples/psycopg3/getting_started/create_db_connection_psycopg.py --mode both

# Test SQLAlchemy 
python samples/sqlalchemy/getting_started/create_db_connection_sqlalchemy.py --mode both
```

## Usage

Choose the driver that best fits your project needs:

- **psycopg3**: Modern PostgreSQL driver (recommended for new projects)
- **psycopg2**: Legacy PostgreSQL driver (for existing projects)  
- **SQLAlchemy**: High-level ORM/Core interface using psycopg3 backend

---

## psycopg2 Driver (Legacy Support)

> **Note**: psycopg2 is in maintenance mode. For new projects, consider using psycopg3 instead.

The psycopg2 integration provides both synchronous (psycopg2) and asynchronous (aiopg) connection support with Azure Entra ID authentication.

### Installation
```bash
pip install "azurepg-entra[psycopg2]"
```

### Synchronous Connection (psycopg2)

```python
from azurepg_entra.psycopg2 import connect_with_entra
from psycopg2 import pool

def main():
    # Direct connection
    conn = connect_with_entra(
        host="your-server.postgres.database.azure.com",
        port=5432,
        dbname="your_database"
    )
    
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT current_user, now()")
            user, time = cur.fetchone()
            print(f"Connected as: {user} at {time}")
    finally:
        conn.close()

    # Connection pooling
    def entra_connection_factory(*args, **kwargs):
        return connect_with_entra(
            host="your-server.postgres.database.azure.com",
            port=5432,
            dbname="your_database"
        )
    
    connection_pool = pool.ThreadedConnectionPool(
        minconn=1, maxconn=5,
        connection_factory=entra_connection_factory
    )
    
    conn = connection_pool.getconn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT current_user")
            print(f"Pool connection as: {cur.fetchone()[0]}")
    finally:
        connection_pool.putconn(conn)
        connection_pool.closeall()

if __name__ == "__main__":
    main()
```

### Asynchronous Connection (aiopg)

```python
import asyncio
from azurepg_entra.psycopg2 import connect_with_entra_async

async def main():
    # Direct async connection
    conn = await connect_with_entra_async(
        host="your-server.postgres.database.azure.com",
        port=5432,
        dbname="your_database"
    )
    
    try:
        async with conn.cursor() as cur:
            await cur.execute("SELECT current_user, now()")
            user, time = await cur.fetchone()
            print(f"Async connected as: {user} at {time}")
    finally:
        conn.close()

if __name__ == "__main__":
    asyncio.run(main())
```

---

## psycopg3 Driver (Recommended)

psycopg3 is the modern, actively developed PostgreSQL driver with native async support and better performance.

### Installation
```bash
pip install "azurepg-entra[psycopg3]"
```

### Synchronous Connection

```python
from azurepg_entra.psycopg3 import SyncEntraConnection
from psycopg_pool import ConnectionPool

def main():
    # Direct connection
    with SyncEntraConnection.connect(
        "postgresql://your-server.postgres.database.azure.com:5432/your_database"
    ) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT current_user, now()")
            user, time = cur.fetchone()
            print(f"Connected as: {user} at {time}")

    # Connection pooling (recommended for production)
    with ConnectionPool(
        conninfo="postgresql://your-server.postgres.database.azure.com:5432/your_database",
        connection_class=SyncEntraConnection,
        min_size=1,   # keep at least 1 connection always open
        max_size=5,   # allow up to 5 concurrent connections
        max_waiting=10,   # seconds to wait if pool is full
    ) as pool:
        with pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT current_user, now()")
                user, time = cur.fetchone()
                print(f"Pool connection as: {user} at {time}")

if __name__ == "__main__":
    main()
```

### Asynchronous Connection

```python
import asyncio
import sys
from azurepg_entra.psycopg3 import AsyncEntraConnection
from psycopg_pool import AsyncConnectionPool

async def main():
    # Direct async connection
    async with await AsyncEntraConnection.connect(
        "postgresql://your-server.postgres.database.azure.com:5432/your_database"
    ) as conn:
        async with conn.cursor() as cur:
            await cur.execute("SELECT current_user, now()")
            user, time = await cur.fetchone()
            print(f"Async connected as: {user} at {time}")

    # Async connection pooling (recommended for production)
    async with AsyncConnectionPool(
        conninfo="postgresql://your-server.postgres.database.azure.com:5432/your_database",
        connection_class=AsyncEntraConnection,
        min_size=1,   # keep at least 1 connection always open
        max_size=5,   # allow up to 5 concurrent connections
        max_waiting=10,   # seconds to wait if pool is full
    ) as pool:
        async with pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute("SELECT current_user, now()")
                user, time = await cur.fetchone()
                print(f"Pool connection as: {user} at {time}")

if __name__ == "__main__":
    # Windows compatibility for async operations
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    
    asyncio.run(main())
```

---

## SQLAlchemy Integration

SQLAlchemy integration uses psycopg3 as the backend driver with automatic Entra ID authentication.

### Installation
```bash
pip install "azurepg-entra[sqlalchemy]"
```

### Synchronous Engine

```python
from azurepg_entra.sqlalchemy import create_entra_engine
from sqlalchemy import text

def main():
    # Create synchronous engine with Entra ID authentication
    engine = create_entra_engine(
        "postgresql+psycopg://your-server.postgres.database.azure.com:5432/your_database"
    )
    
    # Core usage
    with engine.connect() as conn:
        result = conn.execute(text("SELECT current_user, now()"))
        user, time = result.fetchone()
        print(f"SQLAlchemy connected as: {user} at {time}")
    
    # ORM usage
    from sqlalchemy.orm import sessionmaker
    Session = sessionmaker(bind=engine)
    
    with Session() as session:
        result = session.execute(text("SELECT current_database()"))
        db_name = result.scalar()
        print(f"Connected to database: {db_name}")
    
    engine.dispose()

if __name__ == "__main__":
    main()
```

### Asynchronous Engine

```python
import asyncio
import sys
from azurepg_entra.sqlalchemy import create_async_entra_engine
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker

async def main():
    # Create asynchronous engine with Entra ID authentication
    engine = await create_async_entra_engine(
        "postgresql+psycopg://your-server.postgres.database.azure.com:5432/your_database"
    )
    
    # Async Core usage
    async with engine.connect() as conn:
        result = await conn.execute(text("SELECT current_user, now()"))
        user, time = result.fetchone()
        print(f"Async SQLAlchemy connected as: {user} at {time}")
    
    # Async ORM usage
    AsyncSession = async_sessionmaker(engine, expire_on_commit=False)
    
    async with AsyncSession() as session:
        result = await session.execute(text("SELECT current_database()"))
        db_name = result.scalar()
        print(f"Async connected to database: {db_name}")
    
    await engine.dispose()

if __name__ == "__main__":
    # Windows compatibility for async operations
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    
    asyncio.run(main())
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
- **📋 Audit logging**: Authentication events are logged by Azure Database for PostgreSQL

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