"""
Async connection pool utilities for psycopg2/aiopg with connection factory support.

This module provides AsyncEntraConnectionPool, a custom async connection pool
that mimics psycopg2.pool.ThreadedConnectionPool's connection_factory pattern
for asynchronous connections.
"""

import asyncio
from typing import Callable, Any, Awaitable


class AsyncEntraConnectionPool:
    """
    Custom async connection pool that supports connection_factory pattern.
    
    Mimics psycopg2.pool.ThreadedConnectionPool API but for async connections.
    This is needed because:
    1. psycopg2 pools are sync-only
    2. aiopg.create_pool doesn't support connection_factory parameter
    
    Usage:
        async def my_connection_factory():
            return await connect_with_entra_async(host="...", dbname="...")
        
        async with AsyncEntraConnectionPool(my_connection_factory, minconn=1, maxconn=5) as pool:
            conn = await pool.getconn()
            try:
                # Use connection
                pass
            finally:
                pool.putconn(conn)
    """
    
    def __init__(self, connection_factory: Callable[[], Awaitable[Any]], minconn: int = 1, maxconn: int = 5):
        """
        Initialize the async connection pool.
        
        Args:
            connection_factory: Async function that creates and returns a new connection
            minconn: Minimum number of connections to maintain in the pool
            maxconn: Maximum number of connections allowed
        """
        self.connection_factory = connection_factory
        self.minconn = minconn
        self.maxconn = maxconn
        self._pool = []
        self._used = set()
        self._lock = asyncio.Lock()
        self._closed = False
    
    async def __aenter__(self):
        """Context manager entry - pre-populate with minimum connections."""
        for _ in range(self.minconn):
            conn = await self.connection_factory()
            self._pool.append(conn)
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - close all connections."""
        await self.closeall()
    
    async def getconn(self):
        """
        Get a connection from the pool.
        
        Returns:
            Connection object from the pool or newly created
            
        Raises:
            Exception: If pool is exhausted (all maxconn connections in use)
        """
        if self._closed:
            raise Exception("Connection pool is closed")
            
        async with self._lock:
            if self._pool:
                conn = self._pool.pop()
            elif len(self._used) < self.maxconn:
                conn = await self.connection_factory()
            else:
                raise Exception("Connection pool exhausted")
            
            self._used.add(conn)
            return conn
    
    def putconn(self, conn):
        """
        Return a connection to the pool.
        
        Args:
            conn: Connection to return to the pool
        """
        if self._closed:
            return
            
        if conn in self._used:
            self._used.remove(conn)
            if len(self._pool) < self.minconn:
                self._pool.append(conn)
            else:
                # Pool is full, close the connection
                conn.close()
    
    async def closeall(self):
        """Close all connections in the pool."""
        self._closed = True
        
        # Close all pooled connections
        for conn in self._pool:
            conn.close()
        
        # Close all connections in use
        for conn in list(self._used):
            conn.close()
        
        self._pool.clear()
        self._used.clear()