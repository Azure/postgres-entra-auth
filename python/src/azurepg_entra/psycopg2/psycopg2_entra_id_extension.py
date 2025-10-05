# Copyright (c) Microsoft. All rights reserved.
from psycopg2.extensions import connection, parse_dsn, make_dsn
from azurepg_entra.core import get_entra_conninfo

# Define a custom connection class
class SyncEntraConnection(connection):
    """Establishes a synchronous PostgreSQL connection using Entra authentication.

    The method checks for provided credentials. If the 'user' or 'password' are not set
    in the DSN or keyword arguments, it acquires them from Entra via the provided or default credential.

    Parameters:
        dsn: PostgreSQL connection string.
        **kwargs: Keyword arguments including optional 'credential', and optionally 'user' and 'password'.

    Raises:
        ValueError: If the provided credential is not a valid TokenCredential.
    """
    def __init__(self, dsn, **kwargs):
        # Extract current DSN params
        dsn_params = parse_dsn(dsn) if dsn else {}
        
        # Check if user and password are already provided
        has_user = 'user' in dsn_params or 'user' in kwargs
        has_password = 'password' in dsn_params or 'password' in kwargs
        
        # Only get Entra credentials if user or password is missing
        if not has_user or not has_password:
            entra_creds = get_entra_conninfo(None)
            
            # Only update missing credentials
            if not has_user and 'user' in entra_creds:
                dsn_params['user'] = entra_creds['user']
            if not has_password and 'password' in entra_creds:
                dsn_params['password'] = entra_creds['password']
        
        # Update DSN params with any kwargs (kwargs take precedence)
        dsn_params.update(kwargs)
        
        # Create new DSN with updated credentials
        new_dsn = make_dsn(**dsn_params)
        
        # Call parent constructor with updated DSN only
        super().__init__(new_dsn)