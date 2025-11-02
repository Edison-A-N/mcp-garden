# FastAPI MCP SDK

A streamlined SDK for converting FastAPI applications to MCP servers using FastMCP's experimental OpenAPI parser.

> 📚 **Reference**: This SDK is built on top of [FastMCP's FastAPI integration](https://gofastmcp.com/integrations/fastapi#combining-lifespans). For more details on FastMCP's capabilities, authentication, lifespan management, and advanced patterns, see the [official FastMCP documentation](https://gofastmcp.com/integrations/fastapi).


### 🚀 Roadmap
- [ ] MCP authentication support - enabling FastAPI dependency injection for secure MCP endpoints.

## Installation

```bash
git clone <repository>
cd fastapi-mcp-sdk
pip install -e .
```

## Quick Start

### Method 1: Separate Servers (FastAPI + MCP)

FastAPI runs on port 8000, MCP server runs on port 8001:

```bash
cd examples
python run_examples.py fastmcp
```

### Method 2: Integrated Server (Single Port)

Both FastAPI and MCP run on the same port (8000):

```bash
cd examples
python run_examples.py mount
```

### Test FastAPI Only

Run FastAPI without MCP:

```bash
cd examples
python run_examples.py fastapi
```

## Example

See `examples/` directory. Visit http://localhost:8000/docs after running for API documentation.

## API Reference

### FastAPIMCPServer

```python
from fastapi_mcp_sdk import FastAPIMCPServer

# Create MCP server
mcp_server = FastAPIMCPServer()

# Mount to FastAPI app
app_with_mcp = mcp_server.mount_to_fastapi(
    app=app,
    mount_path="/mcp",  # Optional, defaults to "/mcp"
    name="My MCP Server",  # Optional
)
```

**Key features:**
- Uses `httpx.ASGITransport` for direct ASGI calls (no HTTP overhead)
- Automatically extracts OpenAPI spec from FastAPI app and converts to MCP tools
- Full lifecycle management with proper cleanup on shutdown

## Development

```bash
# Setup
pip install -e .

uv run ruff check --fix .
uv run ruff format .
```

## License

MIT License - see LICENSE file for details.
