# Copyright (c) Microsoft. All rights reserved.
from psycopg2.extensions import connection
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