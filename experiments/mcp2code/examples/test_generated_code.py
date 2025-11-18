"""
Test script for generated MCP client code.

This script demonstrates how to use the generated code to interact with MCP servers.
"""

import asyncio
import logging
import sys
import subprocess
from pathlib import Path

# Add generated code to path
generated_path = Path(__file__).parent / "_generated"
if generated_path.exists():
    sys.path.insert(0, str(generated_path.parent))
    # Also add _generated itself to path for absolute imports in __init__.py
    sys.path.insert(0, str(generated_path))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Global variable to store server process
_http_server_process = None


async def test_connection_pool():
    """Test connection pool management."""
    try:
        from _generated.runtime.connection_pool import ConnectionPool

        logger.info("Testing connection pool...")

        pool = ConnectionPool.get_instance()
        logger.info(f"Connection pool instance: {pool}")

        # Test reopening (useful in interactive environments)
        pool.reopen()
        logger.info("✅ Connection pool reopened")

        logger.info("✅ Connection pool tests passed")
        return True

    except ImportError as e:
        logger.warning(f"⚠️  Could not import connection pool: {e}")
        return False
    except Exception as e:
        logger.error(f"❌ Error testing connection pool: {e}", exc_info=True)
        return False


async def test_import_all():
    """Test importing all tools from their respective modules."""
    try:
        # Try importing from tools modules (correct way)
        from _generated.shopping_cart_stdio.tools import (
            shopping_cart_stdio__health_check_health_get,  # noqa: F401
            shopping_cart_stdio__list_products_products,  # noqa: F401
        )
        from _generated.shopping_cart_streamable_http.tools import (
            shopping_cart_streamable_http__health_check_health_get,  # noqa: F401
            shopping_cart_streamable_http__list_products_products,  #  noqa: F401
        )

        logger.info("✅ Successfully imported tools from tools modules")
        return True

    except ImportError as e:
        logger.warning(f"⚠️  Could not import from tools modules: {e}")
        logger.warning("   Make sure to run generate.sh first")
        return False
    except Exception as e:
        logger.error(f"❌ Error testing imports: {e}", exc_info=True)
        return False


async def start_http_server():
    """Start the streamable_http server for testing."""
    global _http_server_process

    if _http_server_process is not None:
        return True  # Server already running

    logger.info("Starting streamable_http server...")
    script_path = Path(__file__).parent / "_run_streamable_http.py"
    script_dir = script_path.parent

    # Start server in background with correct working directory
    _http_server_process = subprocess.Popen(
        [sys.executable, str(script_path)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=str(script_dir),
    )

    # Wait for server to start
    await asyncio.sleep(3)

    if _http_server_process.poll() is not None:
        stdout, stderr = _http_server_process.communicate()
        logger.error(
            f"Server failed to start. stdout: {stdout.decode()}, stderr: {stderr.decode()}"
        )
        _http_server_process = None
        return False

    logger.info("✅ Server started")
    return True


async def stop_http_server():
    """Stop the streamable_http server."""
    global _http_server_process

    if _http_server_process is None:
        return

    logger.info("Stopping streamable_http server...")
    try:
        _http_server_process.terminate()
        _http_server_process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        _http_server_process.kill()
        _http_server_process.wait()
    except Exception as e:
        logger.warning(f"Error stopping server: {e}")
    finally:
        _http_server_process = None
        logger.info("✅ Server stopped")


async def test_shopping_cart_stdio():
    """Test shopping-cart stdio server tools."""
    try:
        # Try to import from stdio server tools module
        try:
            from _generated.shopping_cart_stdio.tools import (
                shopping_cart_stdio__health_check_health_get,
                shopping_cart_stdio__list_products_products,
            )

            server_name = "shopping_cart_stdio"
        except ImportError as e:
            logger.warning(f"⚠️  Could not import shopping_cart_stdio: {e}")
            logger.warning("   Make sure to run generate.sh first")
            return False

        logger.info(f"Testing {server_name} tools...")

        # Test health check (public endpoint, no auth needed)
        logger.info("Calling health check...")
        result = await shopping_cart_stdio__health_check_health_get()
        logger.info(f"Health check result: {result}")

        # Test list products (public endpoint)
        logger.info("Calling list_products...")
        result = await shopping_cart_stdio__list_products_products(page=1, size=5)
        logger.info(f"Products result: {result}")

        logger.info(f"✅ {server_name} tests passed")
        return True

    except Exception as e:
        logger.error(f"❌ Error testing shopping-cart stdio: {e}", exc_info=True)
        return False


async def test_shopping_cart_streamable_http():
    """Test shopping-cart streamable_http server tools.

    Note: Assumes the server is already running (started separately).
    """
    try:
        # Try to import from streamable_http server tools module
        try:
            from _generated.shopping_cart_streamable_http.tools import (
                shopping_cart_streamable_http__health_check_health_get,
                shopping_cart_streamable_http__list_products_products,
            )

            server_name = "shopping_cart_streamable_http"
        except ImportError as e:
            logger.warning(f"⚠️  Could not import shopping_cart_streamable_http: {e}")
            logger.warning("   Make sure to run generate.sh first")
            return False

        logger.info(f"Testing {server_name} tools...")

        # Test health check (public endpoint, no auth needed)
        logger.info("Calling health check...")
        result = await shopping_cart_streamable_http__health_check_health_get()
        logger.info(f"Health check result: {result}")

        # Test list products (public endpoint)
        logger.info("Calling list_products...")
        result = await shopping_cart_streamable_http__list_products_products(page=1, size=5)
        logger.info(f"Products result: {result}")

        logger.info(f"✅ {server_name} tests passed")
        return True

    except Exception as e:
        logger.error(f"❌ Error testing shopping-cart streamable_http: {e}", exc_info=True)
        return False


async def test_error_handling():
    """Test error handling with invalid inputs."""
    try:
        from _generated.shopping_cart_stdio.tools import shopping_cart_stdio__get_product_products

        logger.info("Testing error handling...")

        # Test with invalid product ID (should handle gracefully)
        try:
            result = await shopping_cart_stdio__get_product_products(product_id=99999)
            logger.info(f"Result with invalid input: {result}")
        except Exception as e:
            logger.info(f"Expected error caught: {type(e).__name__}: {e}")

        logger.info("✅ Error handling tests passed")
        return True

    except ImportError as e:
        logger.warning(f"⚠️  Could not import generated code: {e}")
        logger.warning("   Make sure to run generate.sh first")
        return False
    except Exception as e:
        logger.error(f"❌ Error testing error handling: {e}", exc_info=True)
        return False


async def cleanup():
    """Clean up connections."""
    # Close connection pool
    try:
        from _generated.runtime.connection_pool import ConnectionPool

        pool = ConnectionPool.get_instance()
        await pool.close_all()
        logger.info("✅ All connections closed")

    except Exception as e:
        logger.warning(f"⚠️  Error during cleanup: {e}")


async def main():
    """Run all tests."""
    print("=" * 60)
    print("Testing Generated MCP Client Code")
    print("=" * 60)
    print()

    results = []

    # Test 1: Connection pool
    print("Test 1: Connection Pool")
    print("-" * 60)
    results.append(await test_connection_pool())
    print()

    # Test 2: Import all
    print("Test 2: Import All Tools")
    print("-" * 60)
    results.append(await test_import_all())
    print()

    # Test 3: Shopping cart stdio
    print("Test 3: Shopping Cart (stdio)")
    print("-" * 60)
    print("Note: This test uses stdio transport (no server startup needed)")
    print()
    results.append(await test_shopping_cart_stdio())
    print()

    # Test 4: Shopping cart streamable_http
    print("Test 4: Shopping Cart (streamable_http)")
    print("-" * 60)
    print("Note: Assumes the server is already running (started separately)")
    print()
    results.append(await test_shopping_cart_streamable_http())
    print()

    # Test 5: Error handling
    print("Test 5: Error Handling")
    print("-" * 60)
    results.append(await test_error_handling())
    print()

    # Cleanup
    print("Cleanup")
    print("-" * 60)
    await cleanup()
    print()

    # Summary
    print("=" * 60)
    passed = sum(results)
    total = len(results)
    print(f"Test Results: {passed}/{total} passed")
    print("=" * 60)

    if passed == total:
        print("✅ All tests passed!")
        return 0
    else:
        print("⚠️  Some tests failed or were skipped")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
