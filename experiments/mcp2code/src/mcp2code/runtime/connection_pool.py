"""Global connection pool for MCP servers"""

import asyncio
import atexit
import signal
import sys
import threading
import logging
import weakref
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
        self._cleanup_registered: bool = False
        self._cleanup_lock = threading.Lock()
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

                # Register cleanup callback for event loop shutdown
                self._register_async_cleanup()

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
                logger.debug(f"Error closing session for {server_name}: {e}")
            finally:
                if server_name in self._sessions:
                    del self._sessions[server_name]

        # Close transport
        if server_name in self._transports:
            try:
                transport = self._transports[server_name]
                await transport.__aexit__(None, None, None)
            except Exception as e:
                logger.debug(f"Error closing transport for {server_name}: {e}")
            finally:
                if server_name in self._transports:
                    del self._transports[server_name]

    async def close_all(self) -> None:
        """Close all connections"""
        if self._closed:
            return

        self._closed = True
        for server_name in list(self._sessions.keys()):
            try:
                await self.close_server(server_name)
            except Exception as e:
                logger.debug(f"Error closing server {server_name}: {e}")

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

    def _register_async_cleanup(self) -> None:
        """Register async cleanup callback for event loop shutdown.

        This automatically registers a cleanup task that will run when the event loop
        is about to close, ensuring connections are properly closed in the same
        event loop context. This is required for async generators like streamablehttp_client
        that use anyio.create_task_group().
        """
        with self._cleanup_lock:
            if self._cleanup_registered:
                return

            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                # No running loop, can't register cleanup
                return

            # Use weakref to avoid circular references
            pool_ref = weakref.ref(self)

            # Create a cleanup task that monitors the event loop
            # When the event loop is about to close (all other tasks done),
            # this task will run cleanup
            async def _cleanup_monitor():
                """Monitor event loop and cleanup when it's closing"""
                try:
                    # Keep running until event loop closes
                    while True:
                        await asyncio.sleep(0.1)
                        # Check if we should cleanup
                        # When asyncio.run() is about to complete, all user tasks are done
                        # and only system tasks remain
                        try:
                            all_tasks = asyncio.all_tasks(loop)
                            # Filter out this monitor task and other system tasks
                            user_tasks = [
                                t
                                for t in all_tasks
                                if t != asyncio.current_task()
                                and not t.done()
                                and not t.get_name().startswith("_")
                            ]
                            # If no user tasks left and we have connections, cleanup
                            if not user_tasks:
                                pool = pool_ref()
                                if pool and pool._sessions and not pool._closed:
                                    await pool.close_all()
                                    break
                        except Exception:
                            pass
                except asyncio.CancelledError:
                    # Task was cancelled, run cleanup now
                    pool = pool_ref()
                    if pool and not pool._closed:
                        try:
                            await pool.close_all()
                        except Exception as e:
                            logger.debug(f"Error in cleanup monitor: {e}")
                except Exception as e:
                    logger.debug(f"Error in cleanup monitor: {e}")

            try:
                # Create and store the cleanup monitor task
                task = loop.create_task(_cleanup_monitor())
                task.set_name("_mcp_cleanup_monitor")

                # Store task reference to prevent garbage collection
                if not hasattr(loop, "_mcp_cleanup_tasks"):
                    loop._mcp_cleanup_tasks = []
                loop._mcp_cleanup_tasks.append(task)

                self._cleanup_registered = True
            except Exception as e:
                logger.debug(f"Could not register async cleanup: {e}")

    async def cleanup_before_exit(self) -> None:
        """Explicitly cleanup all connections before program exit.

        This should be called at the end of main() function, before asyncio.run() completes.
        This ensures cleanup happens in the same event loop context, which is required
        for async generators like streamablehttp_client that use anyio.create_task_group().

        Note: This is now optional as cleanup is automatically registered when connections
        are created. However, calling this explicitly is still recommended for clarity.

        Example:
            async def main():
                # ... use connections ...
                pool = ConnectionPool.get_instance()
                await pool.cleanup_before_exit()
        """
        if not self._closed:
            await self.close_all()

    def _setup_cleanup(self) -> None:
        """Setup automatic cleanup hooks"""
        # Register atexit handler for normal program exit
        atexit.register(self._cleanup_sync)

        # Use weakref.finalize to ensure cleanup when object is garbage collected
        # This helps catch cases where atexit might not be called
        weakref.finalize(self, self._cleanup_sync)

        def signal_handler(signum, frame):
            # In interactive environments (IPython/Jupyter), don't exit
            # Just close connections but allow reopening
            try:
                # Check if we're in an interactive environment
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
                try:
                    await self.close_server(server_name)
                except Exception:
                    pass
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
            # Try to get or create event loop
            try:
                loop = asyncio.get_running_loop()
                # If loop is running, we can't use it from sync context
                # Just mark as closed - cleanup should be done via cleanup_before_exit()
                logger.debug(
                    "Event loop is running, cleanup should be done via cleanup_before_exit()"
                )
                self._closed = True
            except RuntimeError:
                # No running loop, try to get or create one
                try:
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        self._cleanup_with_new_loop()
                    else:
                        try:
                            loop.run_until_complete(self.close_all())
                        except RuntimeError:
                            self._cleanup_with_new_loop()
                except RuntimeError:
                    self._cleanup_with_new_loop()
        except Exception as e:
            logger.debug(f"Could not close connections during cleanup: {e}")
            self._closed = True

    def _cleanup_with_new_loop(self) -> None:
        """Cleanup using a new event loop"""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(asyncio.wait_for(self.close_all(), timeout=5.0))
        except Exception as e:
            logger.debug(f"Cleanup error: {e}")
            self._closed = True
        finally:
            try:
                pending = asyncio.all_tasks(loop)
                if pending:
                    for task in pending:
                        task.cancel()
                    loop.run_until_complete(
                        asyncio.wait(pending, timeout=1.0, return_when=asyncio.ALL_COMPLETED)
                    )
            except Exception:
                pass
            finally:
                loop.close()
