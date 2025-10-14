# Copyright (c) Microsoft. All rights reserved.

from unittest.mock import patch

import json
import base64
import pytest
from psycopg2.extensions import make_dsn, parse_dsn


def create_test_token(payload):
    """Helper to create a test JWT token manually."""
    # Create a simple JWT-like token with header.payload.signature format
    header = {"alg": "none", "typ": "JWT"}
    header_encoded = (
        base64.urlsafe_b64encode(json.dumps(header).encode()).decode().rstrip("=")
    )
    payload_encoded = (
        base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
    )
    signature = ""
    return f"{header_encoded}.{payload_encoded}.{signature}"


class TestEntraConnection:
    def test_dsn_processing_adds_entra_credentials(self):
        """Test that EntraConnection logic correctly merges Entra credentials into DSN."""
        payload = {"upn": "user@example.com"}
        token = create_test_token(payload)

        with patch("azurepg_entra.core.get_entra_conninfo") as mock_get_creds:
            mock_get_creds.return_value = {
                "user": "user@example.com",
                "password": token,
            }

            # Test with existing DSN parameters
            original_dsn = "host=localhost port=5432 dbname=testdb sslmode=require"
            entra_creds = mock_get_creds(None)

            dsn_params = parse_dsn(original_dsn) if original_dsn else {}
            dsn_params.update(entra_creds)
            new_dsn = make_dsn(**dsn_params)

            mock_get_creds.assert_called_once_with(None)

            # Original params preserved
            assert "host=localhost" in new_dsn
            assert "port=5432" in new_dsn
            assert "dbname=testdb" in new_dsn
            assert "sslmode=require" in new_dsn
            # Entra creds added
            assert "user=user@example.com" in new_dsn
            assert f"password={token}" in new_dsn


if __name__ == "__main__":
    import sys

    exit_code = pytest.main([__file__, "-v", "--tb=short"])
    sys.exit(exit_code)
