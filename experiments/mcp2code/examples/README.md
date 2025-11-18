# mcp2code Examples

This directory contains examples demonstrating how to use `mcp2code` to generate Python packages from MCP configuration files.

## Files

- **`mcp.json.example`** - Example MCP configuration file with shopping cart servers
- **`test_generated_code.py`** - Test script for generated code
- **`_shopping_cart_app.py`** - Example FastAPI application
- **`_run_stdio.py`** - Shopping cart MCP server (stdio transport)
- **`_run_streamable_http.py`** - Shopping cart MCP server (streamable_http transport)
- **`requirements.txt`** - Python dependencies for all examples

## Installation

### Setup Environment with uv (Recommended)

```bash
cd experiments/mcp2code/examples

# 1. Initialize virtual environment
uv venv

# 2. Install dependencies from requirements.txt
uv pip install -r requirements.txt

# 3. Install local mcp2code package in editable mode
uv pip install -e ../.
```

After setup, activate the virtual environment:

```bash
source .venv/bin/activate
```

## Quick Start

Follow these steps to generate and test MCP code:

### Step 1: Prepare Environment

Make sure you've completed the installation steps above and activated the virtual environment:

```bash
cd experiments/mcp2code/examples
source .venv/bin/activate
```

### Step 2: Start MCP Streamable HTTP Server

Start the streamable HTTP server in a terminal (keep it running):

```bash
python _run_streamable_http.py
```

The server will run at:
- FastAPI docs: http://127.0.0.1:8000/docs
- MCP endpoint: http://127.0.0.1:8000/mcp

**Note**: Keep this terminal window open. The server needs to be running for code generation to discover tools from the streamable_http transport.

### Step 3: Generate Code with mcp2code

In another terminal window, navigate to the examples directory and run:

```bash
cd experiments/mcp2code/examples
source .venv/bin/activate

# Generate code from mcp.json.example
mcp2code -c mcp.json.example -f
```

This will:
- Read `mcp.json.example` configuration
- Discover tools from configured MCP servers:
  - **stdio transport**: Automatically starts server via transport layer
  - **streamable_http transport**: Requires server to be running (Step 2)
- Generate Python packages in `_generated/` directory

### Step 4: Generated Code Structure

After generation, the following structure will be created:

```
_generated/
├── __init__.py                          # Exports all tool functions
├── runtime/                             # Runtime support
│   ├── __init__.py
│   └── connection_pool.py
├── shopping_cart_stdio/                 # Shopping cart stdio package
│   ├── __init__.py
│   └── tools.py
└── shopping_cart_streamable_http/       # Shopping cart streamable_http package
    ├── __init__.py
    └── tools.py
```

### Step 5: Test Generated Code

Use the test script to verify the generated code works:

```bash
python test_generated_code.py
```

The test script will:
- Import generated tool functions
- Call MCP servers (both stdio and streamable_http)
- Verify responses and error handling
- Automatically start the streamable_http server if it's not running

**Note**:
- **stdio transport**: No manual server startup needed, transport layer automatically executes the command
- **streamable_http transport**: Server must be running for code generation (Step 2), but test script can start it automatically if needed
- If some servers are unavailable, related tests will be skipped

## Configuration

### mcp.json.example

The example configuration includes two shopping cart MCP servers:

- **shopping-cart-stdio** - Shopping cart server using stdio transport
  - Command: `python -m examples._run_stdio`
  - No server startup needed (handled by transport layer)
  
- **shopping-cart-streamable-http** - Shopping cart server using streamable_http transport
  - URL: `http://127.0.0.1:8000/mcp`
  - Requires server to be running (automatically started by test script)
  - Bearer token: `shopping-cart-api-token-2025`

### Customizing Configuration

1. Copy `mcp.json.example` to `mcp.json`
2. Update server configurations as needed
3. Add or remove servers as needed
4. Run `mcp2code -c mcp.json -o _generated -f` to regenerate code


## Usage Examples

### Import and Use Generated Tools

```python
# Import specific tool from stdio server
from _generated.shopping_cart_stdio.tools import shopping_cart_stdio__health_check_health_get

async def main():
    result = await shopping_cart_stdio__health_check_health_get()
    print(result)

# Import tools from streamable_http server
from _generated.shopping_cart_streamable_http.tools import (
    shopping_cart_streamable_http__health_check_health_get,
    shopping_cart_streamable_http__list_products_products,
)

async def main():
    health = await shopping_cart_streamable_http__health_check_health_get()
    products = await shopping_cart_streamable_http__list_products_products(page=1, size=10)
    print(health, products)
```

### Connection Pool Management

```python
from _generated.runtime.connection_pool import ConnectionPool

# Get singleton instance
pool = ConnectionPool.get_instance()

# Reopen pool (useful in interactive environments after Ctrl+C)
pool.reopen()

# Explicitly close all connections
await pool.close_all()
```

### Error Handling

The generated code includes error handling:

- **JSON parsing errors**: Falls back to raw text if JSON parsing fails
- **Connection errors**: Raises `MCPConnectionError` with descriptive messages
- **Missing configuration**: Raises clear error messages

## Generation Methods

### Method 1: Using CLI (Recommended)

```bash
mcp2code --config mcp.json.example --output _generated --force
```

### Method 2: Using Python API

```python
from mcp2code.generator import MCP2CodeGenerator

# From file path
generator = MCP2CodeGenerator.from_file("mcp.json")
await generator.generate(output_dir="_generated", force=True)

# From JSON string
with open("mcp.json", "r") as f:
    json_data = f.read()
generator = MCP2CodeGenerator.from_json(json_data)
await generator.generate(output_dir="_generated", force=True)

# From dictionary
import json
with open("mcp.json", "r") as f:
    config_dict = json.load(f)
generator = MCP2CodeGenerator.from_dict(config_dict)
await generator.generate(output_dir="_generated", force=True)
```

## Advanced Usage

### Discover Tools Before Generation

```python
from mcp2code.generator import MCP2CodeGenerator

generator = MCP2CodeGenerator.from_file("mcp.json")

# Discover tools first
discovered = await generator.discover_all_tools()

for server_name, tools in discovered.items():
    print(f"{server_name}: {len(tools)} tools")
    for tool in tools:
        print(f"  - {tool['name']}")

# Then generate
await generator.generate(output_dir="_generated", force=True)
```

### Manual Server Startup

#### stdio Server

**No manual startup needed**. The stdio transport automatically executes the command to start the server.

If you want to test the stdio server separately:

```bash
cd experiments/mcp2code/examples
python _run_stdio.py
```

**Note**: The stdio server communicates via stdin/stdout, so running it directly will wait for input.

#### streamable_http Server

Must be started manually (required for code generation and testing):

```bash
cd experiments/mcp2code/examples
python _run_streamable_http.py
```

The server runs at:
- FastAPI docs: http://127.0.0.1:8000/docs
- MCP endpoint: http://127.0.0.1:8000/mcp

**Important**:
- For code generation, the streamable_http server must be running first
- The test script can automatically start the server if it's not running
- Use Ctrl+C to stop the server

## Troubleshooting

### Import Errors

If you get import errors when running tests:

1. Make sure you've run `mcp2code` first
2. Check that `_generated/` directory exists
3. Verify that the generated code is in your Python path

### Connection Errors

If tools fail to connect:

1. **For stdio transport**: Check that the command path in `mcp.json.example` is correct
2. **For streamable_http transport**: 
   - Ensure the server is running (test script starts it automatically)
   - Check that the URL and port are correct
   - Verify Bearer token is set correctly
3. Check logs for specific error messages

### Generation Errors

If code generation fails:

1. Check that `mcp.json.example` is valid JSON
2. Verify that MCP servers are accessible
3. For stdio servers, ensure the command can be executed
4. Check logs for specific error messages
5. Ensure all required dependencies are installed (`uv sync`)

## Next Steps

- Read the main [README.md](../README.md) for more details
- Explore generated code in `_generated/` directory
- Customize `mcp.json.example` for your use case

