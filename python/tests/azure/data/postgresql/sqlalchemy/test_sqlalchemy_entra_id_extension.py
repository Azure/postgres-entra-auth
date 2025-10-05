# Copyright (c) Microsoft. All rights reserved.
import pytest
from unittest.mock import Mock, patch

class TestEnableEntraAuthentication:
    def test_sync_authentication_function_registration(self):
        """Test that enable_entra_authentication registers event listener successfully."""
        mock_engine = Mock()
        
        with patch('sqlalchemy.event.listens_for') as mock_event_listener:
            from azurepg_entra.sqlalchemy import enable_entra_authentication
            enable_entra_authentication(mock_engine)
            
            # Verify event listener was registered with correct parameters
            mock_event_listener.assert_called_once_with(mock_engine, "do_connect")

    def test_provide_token_method(self):
        """Test the provide_token event handler method directly."""
        mock_engine = Mock()
        
        # Capture the event handler function
        captured_handler = None
        def capture_handler(engine, event_name):
            def decorator(func):
                nonlocal captured_handler
                captured_handler = func
                return func
            return decorator
        
        with patch('sqlalchemy.event.listens_for', side_effect=capture_handler):
            with patch('azurepg_entra.sqlalchemy.sqlalchemy_entra_id_extension.get_entra_conninfo') as mock_get_creds:
                mock_get_creds.return_value = {"user": "test@example.com", "password": "test_token"}
                
                from azurepg_entra.sqlalchemy import enable_entra_authentication
                enable_entra_authentication(mock_engine)
                
                # Test the captured handler directly
                mock_cparams = {}
                captured_handler(None, None, None, mock_cparams)
                
                # Verify credentials were added
                mock_get_creds.assert_called_once_with(None)
                assert mock_cparams["user"] == "test@example.com"
                assert mock_cparams["password"] == "test_token"

    def test_provide_token_skips_existing_credentials(self):
        """Test that provide_token skips when credentials already exist."""
        mock_engine = Mock()
        
        # Capture the event handler function
        captured_handler = None
        def capture_handler(engine, event_name):
            def decorator(func):
                nonlocal captured_handler
                captured_handler = func
                return func
            return decorator
        
        with patch('sqlalchemy.event.listens_for', side_effect=capture_handler):
            with patch('azurepg_entra.sqlalchemy.sqlalchemy_entra_id_extension.get_entra_conninfo') as mock_get_creds:
                from azurepg_entra.sqlalchemy import enable_entra_authentication
                enable_entra_authentication(mock_engine)
                
                # Test with existing credentials
                mock_cparams = {"user": "existing@example.com", "password": "existing_password"}
                captured_handler(None, None, None, mock_cparams)
                
                # Verify get_entra_conninfo was not called
                mock_get_creds.assert_not_called()
                assert mock_cparams["user"] == "existing@example.com"
                assert mock_cparams["password"] == "existing_password"

    def test_async_authentication_function_registration(self):
        """Test that enable_entra_authentication_async registers event listener successfully."""
        mock_async_engine = Mock()
        mock_sync_engine = Mock()
        mock_async_engine.sync_engine = mock_sync_engine
        
        with patch('sqlalchemy.event.listens_for') as mock_event_listener:
            from azurepg_entra.sqlalchemy import enable_entra_authentication_async
            enable_entra_authentication_async(mock_async_engine)
            
            # Verify event listener was registered on sync_engine
            mock_event_listener.assert_called_once_with(mock_sync_engine, "do_connect")

    def test_provide_token_async_method(self):
        """Test the provide_token_async event handler method directly."""
        mock_async_engine = Mock()
        mock_sync_engine = Mock()
        mock_async_engine.sync_engine = mock_sync_engine
        
        # Capture the event handler function
        captured_handler = None
        def capture_handler(engine, event_name):
            def decorator(func):
                nonlocal captured_handler
                captured_handler = func
                return func
            return decorator
        
        with patch('sqlalchemy.event.listens_for', side_effect=capture_handler):
            with patch('azurepg_entra.sqlalchemy.sqlalchemy_entra_id_extension.get_entra_conninfo_async') as mock_get_creds_async:
                with patch('asyncio.run') as mock_asyncio_run:
                    mock_get_creds_async.return_value = {"user": "test@example.com", "password": "test_token"}
                    mock_asyncio_run.return_value = {"user": "test@example.com", "password": "test_token"}
                    
                    from azurepg_entra.sqlalchemy import enable_entra_authentication_async
                    enable_entra_authentication_async(mock_async_engine)
                    
                    # Test the captured handler directly
                    mock_cparams = {}
                    captured_handler(None, None, None, mock_cparams)
                    
                    # Verify credentials were added (either through direct call or asyncio.run)
                    assert mock_cparams["user"] == "test@example.com"
                    assert mock_cparams["password"] == "test_token"

    def test_provide_token_async_skips_existing_credentials(self):
        """Test that provide_token_async skips when credentials already exist."""
        mock_async_engine = Mock()
        mock_sync_engine = Mock()
        mock_async_engine.sync_engine = mock_sync_engine
        
        # Capture the event handler function
        captured_handler = None
        def capture_handler(engine, event_name):
            def decorator(func):
                nonlocal captured_handler
                captured_handler = func
                return func
            return decorator
        
        with patch('sqlalchemy.event.listens_for', side_effect=capture_handler):
            with patch('azurepg_entra.sqlalchemy.sqlalchemy_entra_id_extension.get_entra_conninfo') as mock_get_creds:
                from azurepg_entra.sqlalchemy import enable_entra_authentication_async
                enable_entra_authentication_async(mock_async_engine)
                
                # Test with existing credentials
                mock_cparams = {"user": "existing@example.com", "password": "existing_password"}
                captured_handler(None, None, None, mock_cparams)
                
                # Verify get_entra_conninfo was not called
                mock_get_creds.assert_not_called()
                assert mock_cparams["user"] == "existing@example.com"
                assert mock_cparams["password"] == "existing_password"


if __name__ == "__main__":
    import sys
    exit_code = pytest.main([__file__, "-v", "--tb=short"])
    sys.exit(exit_code)