# Copyright (c) Microsoft. All rights reserved.
import sys
from psycopg2.extensions import connection
import psycopg2
import asyncio
import aiopg

from azurepg_entra.core import get_entra_conninfo, get_entra_conninfo_async

# Define a custom connection class
class SyncEntraConnection(connection):
    def __init__(self, dsn, **kwargs):
        # Get Entra credentials before establishing connection
        entra_creds = get_entra_conninfo(None)
        
        # Extract current DSN params and update with Entra credentials
        from psycopg2.extensions import parse_dsn, make_dsn
        dsn_params = parse_dsn(dsn) if dsn else {}
        dsn_params.update(entra_creds)  # This should include 'user' and 'password'
        
        # Create new DSN with Entra credentials
        new_dsn = make_dsn(**dsn_params)
        
        # Call parent constructor with updated DSN
        super().__init__(new_dsn, **kwargs)

    def cursor(self, *args, **kwargs):
        return super().cursor(*args, **kwargs)
    
# For async, we need a different approach - use a factory function
async def create_async_entra_connection(**conn_params):
    # Get Entra credentials asynchronously
    entra_creds = await get_entra_conninfo_async(None)
    
    # Update connection parameters with Entra credentials
    conn_params.update(entra_creds)
    
    # Create connection with updated parameters
    conn = await aiopg.connect(**conn_params)
    return conn
    
# Define a custom connection class
# class AsyncEntraConnection(connection):
#     async def __init__(self, dsn, **kwargs):
#         # Get Entra credentials before establishing connection
#         entra_creds = await get_entra_conninfo_async()
        
#         # Extract current DSN params and update with Entra credentials
#         from psycopg2.extensions import parse_dsn, make_dsn
#         dsn_params = parse_dsn(dsn) if dsn else {}
#         dsn_params.update(entra_creds)  # This should include 'user' and 'password'
        
#         # Create new DSN with Entra credentials
#         new_dsn = make_dsn(**dsn_params)
        
#         # Call parent constructor with updated DSN
#         super().__init__(new_dsn, **kwargs)

#     def cursor(self, *args, **kwargs):
#         return super().cursor(*args, **kwargs)

def sync_test():
    # Use it as a factory
    conn = psycopg2.connect(
        dbname="postgres",
        host="pg-mjm-dev1.postgres.database.azure.com",
        connection_factory=SyncEntraConnection
    )
    cur = conn.cursor()
    cur.execute("SELECT 1")
    print(cur.fetchone())

async def async_test():
    # Use the factory function instead
    conn = await create_async_entra_connection(
        dbname="postgres",
        host="pg-mjm-dev1.postgres.database.azure.com"
    )
    cur = await conn.cursor()
    await cur.execute("SELECT 1")
    result = await cur.fetchone()
    print(result)
    conn.close()

if __name__ == "__main__":
    sync_test()
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(async_test())