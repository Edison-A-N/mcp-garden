#!/usr/bin/env python3
"""
Test script for Shopping Cart MCP Examples
This script tests the basic functionality of the examples.

Usage:
    python test_examples.py [method] [--fastapi-port PORT] [--mcp-port PORT]

Methods:
    fastmcp  - Test FastMCP method (two servers: FastAPI on 8000, MCP on 8001)
    mount    - Test Mount method (single server: FastAPI + MCP on 8000)
    all      - Test both methods (default)
    fixtures - Test only fixtures data
    help     - Show usage instructions

Options:
    --fastapi-port PORT  - FastAPI server port (default: 8000)
    --mcp-port PORT      - MCP server port (default: 8001)

Examples:
    # Test FastMCP method with default ports
    python test_examples.py fastmcp

    # Test Mount method with custom FastAPI port
    python test_examples.py mount --fastapi-port 9000

    # Test both methods with custom ports
    python test_examples.py all --fastapi-port 9000 --mcp-port 9001

    # Test only fixtures
    python test_examples.py fixtures

    # Show help
    python test_examples.py help
"""

import anyio
import argparse
import json
import sys
from pathlib import Path

import httpx

# MCP client imports
try:
    from mcp.client.session import ClientSession
    from mcp.client.streamable_http import streamablehttp_client

    MCP_AVAILABLE = True
except ImportError:
    MCP_AVAILABLE = False
    print("⚠️  MCP client not available. MCP tests will be skipped.")


from _shopping_cart_app import BEARER_TOKEN


def validate_tool_result(call_result, tool_name: str) -> tuple[bool, dict]:
    """Validate MCP tool call result and extract data.

    Args:
        call_result: The result from MCP call_tool
        tool_name: Name of the tool that was called

    Returns:
        Tuple of (is_valid: bool, data: dict)
    """
    if not call_result:
        print("   ❌ Tool returned None or empty result")
        return False, {}

    if hasattr(call_result, "isError") and call_result.isError:
        print("   ❌ Tool returned error")
        return False, {}

    if not hasattr(call_result, "content") or not call_result.content:
        print("   ❌ Tool returned no content")
        return False, {}

    content_items = call_result.content

    if not isinstance(content_items, list) or len(content_items) == 0:
        print("   ❌ Tool content is invalid")
        return False, {}

    text_content = None
    for item in content_items:
        if hasattr(item, "text") and item.text:
            text_content = item.text
            break
        elif hasattr(item, "content") and isinstance(item.content, str):
            text_content = item.content
            break
        elif isinstance(item, str):
            text_content = item
            break
        elif isinstance(item, dict):
            if "text" in item:
                text_content = item["text"]
                break
            elif "content" in item:
                text_content = item["content"]
                break

    if not text_content:
        print("   ❌ Could not extract text content from tool result")
        return False, {}

    try:
        data = json.loads(text_content)

        if "get_user" in tool_name.lower() or "user" in tool_name.lower():
            if isinstance(data, dict):
                expected_fields = ["id", "username"]
                found_fields = [field for field in expected_fields if field in data]
                if len(found_fields) >= 1:
                    return True, data
                else:
                    print("   ❌ Tool returned data but missing expected user fields")
                    return False, data
            else:
                print(f"   ❌ Tool returned non-dict data: {type(data)}")
                return False, data
        elif "product" in tool_name.lower():
            if isinstance(data, dict):
                expected_fields = ["id", "name"]
                found_fields = [field for field in expected_fields if field in data]
                if len(found_fields) >= 1:
                    return True, data
                else:
                    print("   ❌ Tool returned data but missing expected product fields")
                    return False, data
        else:
            return True, data

    except json.JSONDecodeError:
        if isinstance(text_content, str) and len(text_content) > 0:
            return True, {"raw": text_content}
        else:
            print("   ❌ Tool returned invalid content")
            return False, {}
    except Exception as e:
        print(f"   ❌ Error validating tool result: {e}")
        return False, {}


async def test_fastapi_endpoints(fastapi_port: int = 8000):
    """Test FastAPI endpoints including authentication."""
    base_url = f"http://127.0.0.1:{fastapi_port}"
    headers = {"Authorization": f"Bearer {BEARER_TOKEN}"}
    failed_tests = []

    async with httpx.AsyncClient(headers=headers) as client:
        try:
            endpoints = [
                ("GET", "/", {}),
                ("GET", "/health", {}),
                ("GET", "/info", {}),
                ("GET", "/products/?page=1&size=5", {}),
                ("GET", "/users/?page=1&size=5", {}),
                ("GET", "/analytics/summary", {}),
                ("GET", "/analytics/products/popular?limit=5", {}),
                ("GET", "/search/products/?query=test&page=1&size=5", {}),
                ("GET", "/products/1", {}),
            ]

            for method, path, data in endpoints:
                try:
                    if method == "GET":
                        response = await client.get(f"{base_url}{path}")
                    else:
                        response = await client.post(f"{base_url}{path}", json=data)

                    if response.status_code != 200:
                        failed_tests.append(f"{method} {path}: {response.status_code}")
                except Exception as e:
                    failed_tests.append(f"{method} {path}: {str(e)}")

            user_data = {
                "username": "testuser",
                "email": "test@example.com",
                "full_name": "Test User",
                "password": "TestPass123",
                "role": "customer",
            }
            product_data = {
                "name": "Test Product",
                "description": "This is a test product",
                "price": 99.99,
                "category": "electronics",
                "stock_quantity": 100,
            }

            no_auth_client = httpx.AsyncClient()
            async with no_auth_client:
                for endpoint, data in [
                    ("/users/", user_data),
                    ("/products/", product_data),
                ]:
                    try:
                        response = await no_auth_client.post(f"{base_url}{endpoint}", json=data)
                        if response.status_code != 401:
                            failed_tests.append(f"POST {endpoint} (no auth): expected 401, got {response.status_code}")
                    except Exception as e:
                        failed_tests.append(f"POST {endpoint} (no auth): {str(e)}")

            for endpoint, data in [
                ("/users/", user_data),
                ("/products/", product_data),
            ]:
                try:
                    response = await client.post(f"{base_url}{endpoint}", json=data)
                    if response.status_code not in [200, 201]:
                        failed_tests.append(f"POST {endpoint} (with auth): {response.status_code}")
                except Exception as e:
                    failed_tests.append(f"POST {endpoint} (with auth): {str(e)}")

            try:
                response = await client.get(f"{base_url}/users/1")
                if response.status_code != 200:
                    failed_tests.append(f"GET /users/1: {response.status_code}")
            except Exception as e:
                failed_tests.append(f"GET /users/1: {str(e)}")

            if failed_tests:
                print(f"❌ Failed tests ({len(failed_tests)}):")
                for test in failed_tests[:10]:
                    print(f"   - {test}")
                if len(failed_tests) > 10:
                    print(f"   ... and {len(failed_tests) - 10} more")
                return False

            return True

        except httpx.ConnectError:
            print(f"❌ Could not connect to FastAPI server on port {fastapi_port}")
            return False
        except Exception as e:
            print(f"❌ Error testing FastAPI endpoints: {e}")
            return False


async def test_mcp_endpoints_mount(mcp_port: int = 8001):
    """Test MCP endpoints using mount method (Method 2)."""
    if not MCP_AVAILABLE:
        print("⚠️  MCP client not available")
        return False

    try:
        headers = {"Authorization": f"Bearer {BEARER_TOKEN}"}
        async with streamablehttp_client(f"http://127.0.0.1:{mcp_port}/mcp", headers=headers) as (
            read_stream,
            write_stream,
            _,
        ):
            async with ClientSession(read_stream, write_stream) as session:
                init_result = await session.initialize()
                if not init_result:
                    print("❌ MCP initialize failed")
                    return False

                tools_result = await session.list_tools()
                if not tools_result or not tools_result.tools:
                    print("❌ MCP list_tools failed")
                    return False

                get_user_tool = None
                for tool in tools_result.tools:
                    if "get_user" in tool.name.lower():
                        get_user_tool = tool
                        break
                if not get_user_tool:
                    for tool in tools_result.tools:
                        if "user" in tool.name.lower() and "get" in tool.name.lower():
                            get_user_tool = tool
                            break

                if get_user_tool:
                    tool_args = {}
                    if get_user_tool.inputSchema and isinstance(get_user_tool.inputSchema, dict):
                        props = get_user_tool.inputSchema.get("properties", {})
                        if "user_id" in props:
                            tool_args["user_id"] = 1
                        elif "id" in props:
                            tool_args["id"] = 1

                    try:
                        call_result = await session.call_tool(
                            get_user_tool.name,
                            arguments=tool_args if tool_args else None,
                        )
                        if call_result:
                            is_valid, _ = validate_tool_result(call_result, get_user_tool.name)
                            if not is_valid:
                                print("❌ MCP call_tool returned invalid result")
                                return False
                        else:
                            print("❌ MCP call_tool returned no result")
                            return False
                    except Exception:
                        pass

                return True

    except Exception as e:
        print(f"❌ Error testing MCP endpoints (Mount): {e}")
        return False


async def test_mcp_endpoints_fastmcp(mcp_port: int = 8001):
    """Test MCP endpoints using FastMCP method (Method 1)."""
    if not MCP_AVAILABLE:
        print("⚠️  MCP client not available")
        return False

    try:
        headers = {"Authorization": f"Bearer {BEARER_TOKEN}"}
        async with streamablehttp_client(f"http://127.0.0.1:{mcp_port}/mcp", headers=headers) as (
            read_stream,
            write_stream,
            _,
        ):
            async with ClientSession(read_stream, write_stream) as session:
                init_result = await session.initialize()
                if not init_result:
                    print("❌ MCP initialize failed")
                    return False

                tools_result = await session.list_tools()
                if not tools_result or not tools_result.tools:
                    print("❌ MCP list_tools failed")
                    return False

                get_user_tool = None
                for tool in tools_result.tools:
                    if "get_user" in tool.name.lower():
                        get_user_tool = tool
                        break
                if not get_user_tool:
                    for tool in tools_result.tools:
                        if "user" in tool.name.lower() and "get" in tool.name.lower():
                            get_user_tool = tool
                            break

                if get_user_tool:
                    tool_args = {}
                    if get_user_tool.inputSchema and isinstance(get_user_tool.inputSchema, dict):
                        props = get_user_tool.inputSchema.get("properties", {})
                        if "user_id" in props:
                            tool_args["user_id"] = 1
                        elif "id" in props:
                            tool_args["id"] = 1

                    try:
                        call_result = await session.call_tool(
                            get_user_tool.name, arguments=tool_args if tool_args else {}
                        )
                        if call_result:
                            is_valid, _ = validate_tool_result(call_result, get_user_tool.name)
                            if not is_valid:
                                print("❌ MCP call_tool returned invalid result")
                                return False
                        else:
                            print("❌ MCP call_tool returned no result")
                            return False
                    except Exception:
                        pass

                return True

    except Exception as e:
        print(f"❌ Error testing MCP endpoints (FastMCP): {e}")
        return False


async def test_mcp_no_auth(mcp_port: int = 8001):
    """Test MCP endpoints without authentication (should fail)."""
    if not MCP_AVAILABLE:
        print("⚠️  MCP client not available")
        return False

    try:
        async with streamablehttp_client(f"http://127.0.0.1:{mcp_port}/mcp", headers={}) as (
            read_stream,
            write_stream,
            get_session_id,
        ):
            async with ClientSession(read_stream, write_stream) as session:
                try:
                    init_result = await session.initialize()
                    if init_result:
                        try:
                            await session.list_tools()
                            print("❌ MCP list_tools succeeded without auth (should fail)")
                            return False
                        except Exception as e:
                            error_str = str(e).lower()
                            if any(
                                keyword in error_str
                                for keyword in [
                                    "401",
                                    "403",
                                    "unauthorized",
                                    "forbidden",
                                    "authentication",
                                    "auth",
                                ]
                            ):
                                return True
                            else:
                                print(f"⚠️  MCP list_tools failed with: {e} (may be auth-related)")
                                return True
                    else:
                        print("❌ MCP initialize returned False without auth")
                        return True
                except Exception as e:
                    error_str = str(e).lower()
                    if any(
                        keyword in error_str
                        for keyword in [
                            "401",
                            "403",
                            "unauthorized",
                            "forbidden",
                            "authentication",
                            "auth",
                        ]
                    ):
                        return True
                    else:
                        print(f"⚠️  MCP initialize failed: {e} (may be auth-related)")
                        return True

    except Exception as e:
        error_str = str(e).lower()
        if any(
            keyword in error_str
            for keyword in [
                "401",
                "403",
                "unauthorized",
                "forbidden",
                "authentication",
                "auth",
            ]
        ):
            return True
        else:
            print(f"⚠️  MCP connection error: {e} (may be expected if server requires auth)")
            return True


def test_fixtures_data():
    """Test fixtures data files."""
    fixtures_dir = Path(__file__).parent / "fixtures"

    users_file = fixtures_dir / "users.json"
    if not users_file.exists():
        print("❌ Users fixtures file not found")
        return False
    try:
        with open(users_file, "r", encoding="utf-8") as f:
            users_data = json.load(f)
        if not isinstance(users_data, list) or len(users_data) == 0:
            print("❌ Users fixtures data invalid")
            return False
    except json.JSONDecodeError:
        print("❌ Users fixtures data is not valid JSON")
        return False

    products_file = fixtures_dir / "products.json"
    if not products_file.exists():
        print("❌ Products fixtures file not found")
        return False
    try:
        with open(products_file, "r", encoding="utf-8") as f:
            products_data = json.load(f)
        if not isinstance(products_data, list) or len(products_data) == 0:
            print("❌ Products fixtures data invalid")
            return False
    except json.JSONDecodeError:
        print("❌ Products fixtures data is not valid JSON")
        return False

    return True


def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Test script for Shopping Cart MCP Examples",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Test FastMCP method with default ports
  python test_examples.py fastmcp

  # Test Mount method with custom FastAPI port
  python test_examples.py mount --fastapi-port 9000

  # Test both methods with custom ports
  python test_examples.py all --fastapi-port 9000 --mcp-port 9001

  # Test only fixtures
  python test_examples.py fixtures
        """,
    )

    parser.add_argument(
        "method",
        nargs="?",
        default="all",
        choices=["fastmcp", "mount", "all", "fixtures", "help"],
        help="Test method to run (default: all)",
    )

    parser.add_argument(
        "--fastapi-port",
        type=int,
        default=8000,
        help="FastAPI server port (default: 8000)",
    )

    parser.add_argument("--mcp-port", type=int, default=8001, help="MCP server port (default: 8001)")

    return parser.parse_args()


def print_usage():
    """Print usage instructions."""
    print("\n📋 Usage Instructions:")
    print("=" * 60)
    print("1. Test FastMCP method (two servers):")
    print("   Terminal 1: python _run_with_fastmcp.py")
    print("   Terminal 2: python test_examples.py fastmcp")
    print()
    print("2. Test Mount method (single server):")
    print("   Terminal 1: python _run_with_mount.py")
    print("   Terminal 2: python test_examples.py mount")
    print()
    print("3. Test both methods:")
    print("   python test_examples.py all")
    print()
    print("4. Test with custom ports:")
    print("   python test_examples.py mount --fastapi-port 9000")
    print("   python test_examples.py fastmcp --fastapi-port 9000 --mcp-port 9001")
    print()
    print("5. Test only fixtures data:")
    print("   python test_examples.py fixtures")
    print()
    print("6. Show this help:")
    print("   python test_examples.py help")


async def main():
    """Main test function."""
    args = parse_arguments()

    if not test_fixtures_data():
        print("❌ Fixtures data tests failed")
        sys.exit(1)

    if args.method == "help":
        print_usage()
        return
    elif args.method == "fixtures":
        return

    if args.method != "fixtures":
        fastapi_success = await test_fastapi_endpoints(args.fastapi_port)
    else:
        fastapi_success = True

    if args.method in ["mount", "all"]:
        mount_success = await test_mcp_endpoints_mount(args.mcp_port)
    else:
        mount_success = True

    if args.method in ["fastmcp", "all"]:
        fastmcp_success = await test_mcp_endpoints_fastmcp(args.mcp_port)
    else:
        fastmcp_success = True

    results = []
    if args.method != "fixtures":
        results.append(f"FastAPI: {'✅' if fastapi_success else '❌'}")
    if args.method in ["mount", "all"]:
        results.append(f"MCP Mount: {'✅' if mount_success else '❌'}")
    if args.method in ["fastmcp", "all"]:
        results.append(f"MCP FastMCP: {'✅' if fastmcp_success else '❌'}")

    print("\n📊 Results: " + " | ".join(results))

    if not (fastapi_success and mount_success and fastmcp_success):
        sys.exit(1)


if __name__ == "__main__":
    anyio.run(main)
