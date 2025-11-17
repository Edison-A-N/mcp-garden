"""Global connection pool for MCP servers"""

import asyncio
import atexit
import signal
import threading
import logging
from typing import Dict, Any, Optional
from mcp import ClientSession

from mcp2code.config import MCPServerConfig
from mcp2code.transport import create_transport

logger = logging.getLogger(__name__)


class MCPConnectionError(Exception):
    """MCP connection error"""

    pass


class ConnectionPool:
    """Global MCP connection pool (singleton)"""

    _instance: Optional["ConnectionPool"] = None
    _lock = threading.Lock()

    def __init__(self):
        self._sessions: Dict[str, ClientSession] = {}
        self._transports: Dict[str, Any] = {}
        self._locks: Dict[str, asyncio.Lock] = {}
        self._configs: Dict[str, MCPServerConfig] = {}
        self._closed: bool = False
        self._setup_cleanup()

    @classmethod
    def get_instance(cls) -> "ConnectionPool":
        """Get global singleton instance"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def register_config(self, server_name: str, config: MCPServerConfig) -> None:
        """Register server configuration"""
        # Auto-reopen if closed (useful in interactive environments)
        if self._closed:
            logger.info("Connection pool was closed, auto-reopening for config registration")
            self._closed = False
        self._configs[server_name] = config
        if server_name not in self._locks:
            self._locks[server_name] = asyncio.Lock()

    async def get_session(self, server_name: str) -> ClientSession:
        """Get or create server connection (lazy)"""
        # Auto-reopen if closed but config exists (useful in interactive environments)
        if self._closed:
            if server_name in self._configs:
                logger.info(
                    f"Connection pool was closed, auto-reopening for server '{server_name}'"
                )
                self._closed = False
            else:
                raise RuntimeError("Connection pool is closed")

        # Return existing session if available
        if server_name in self._sessions:
            return self._sessions[server_name]

        # Check if config is registered
        if server_name not in self._configs:
            raise MCPConnectionError(
                f"Server '{server_name}' not configured. "
                f"Available servers: {list(self._configs.keys())}"
            )

        # Acquire lock for this server
        lock = self._locks.get(server_name)
        if lock is None:
            lock = asyncio.Lock()
            self._locks[server_name] = lock

        async with lock:
            # Double-check after acquiring lock
            if server_name in self._sessions:
                return self._sessions[server_name]

            # Create new connection
            try:
                config = self._configs[server_name]
                transport, read, write = await create_transport(config)
                session = ClientSession(read, write)

                # Enter async context to start the read task
                # This is necessary for ClientSession to work properly
                await session.__aenter__()
                await session.initialize()

                self._transports[server_name] = transport
                self._sessions[server_name] = session
                logger.info(f"Connected to MCP server: {server_name}")
                return session
            except Exception as e:
                raise MCPConnectionError(f"Failed to connect to server '{server_name}': {e}") from e

    async def close_server(self, server_name: str) -> None:
        """Close connection for a specific server"""
        # Close session first (exit async context)
        if server_name in self._sessions:
            try:
                session = self._sessions[server_name]
                await session.__aexit__(None, None, None)
            except Exception as e:
                logger.error(f"Error closing session for {server_name}: {e}")
            del self._sessions[server_name]

        # Close transport
        if server_name in self._transports:
            try:
                transport = self._transports[server_name]
                await transport.__aexit__(None, None, None)
            except Exception as e:
                logger.error(f"Error closing transport for {server_name}: {e}")
            del self._transports[server_name]

    async def close_all(self) -> None:
        """Close all connections"""
        if self._closed:
            return

        self._closed = True
        for server_name in list(self._sessions.keys()):
            await self.close_server(server_name)

        self._sessions.clear()
        self._transports.clear()
        logger.info("All MCP connections closed")

    def reopen(self) -> None:
        """Reopen the connection pool after it has been closed.

        This is useful in interactive environments (like IPython) where
        the pool might be closed due to signal handlers (e.g., Ctrl+C).
        """
        if not self._closed:
            return

        self._closed = False
        logger.info("Connection pool reopened")

    def _setup_cleanup(self) -> None:
        """Setup automatic cleanup hooks"""
        atexit.register(self._cleanup_sync)

        def signal_handler(signum, frame):
            # In interactive environments (IPython/Jupyter), don't exit
            # Just close connections but allow reopening
            try:
                # Check if we're in an interactive environment
                import sys

                is_interactive = (
                    hasattr(sys, "ps1")  # Standard Python REPL
                    or "IPython" in sys.modules  # IPython
                    or any("jupyter" in mod.lower() for mod in sys.modules.keys())  # Jupyter
                )
                if is_interactive:
                    # Interactive environment: close connections but don't mark as permanently closed
                    # This allows the pool to be reopened later
                    logger.info("Signal received in interactive environment, closing connections")
                    self._cleanup_sync_soft()
                    return
            except Exception:
                pass

            # Non-interactive: full cleanup and exit
            self._cleanup_sync()
            sys.exit(0)

        signal.signal(signal.SIGTERM, signal_handler)
        signal.signal(signal.SIGINT, signal_handler)

    def _cleanup_sync_soft(self) -> None:
        """Soft cleanup: close connections but don't mark pool as permanently closed"""
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        async def _soft_close():
            for server_name in list(self._sessions.keys()):
                await self.close_server(server_name)
            self._sessions.clear()
            self._transports.clear()
            # Don't set _closed = True, allowing pool to be reused

        if loop.is_running():
            loop.create_task(_soft_close())
        else:
            loop.run_until_complete(_soft_close())

    def _cleanup_sync(self) -> None:
        """Synchronous cleanup wrapper"""
        if self._closed:
            return

        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        if loop.is_running():
            # If loop is running, create task
            loop.create_task(self.close_all())
        else:
            # Otherwise run directly
            loop.run_until_complete(self.close_all())
