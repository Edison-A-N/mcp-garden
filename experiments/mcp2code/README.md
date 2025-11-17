# mcp2code

![Python](https://img.shields.io/badge/python-3.11+-blue.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)
![Version](https://img.shields.io/badge/version-0.1.0-orange.svg)

A tool that automatically generates Python packages from `mcp.json` configuration files. Each MCP server corresponds to an independent Python package, and each tool corresponds to an async function.

## Features

- **Independent packages**: Each server generates a separate package
- **Lazy connections**: Connections established on first call
- **Global connection pool**: Shared singleton with automatic cleanup
- **Type hints**: Auto-generated TypedDict from inputSchema/outputSchema
- **Function naming**: `server__tool_name` format
- **Tool filtering**: Only generates tools with JSON outputSchema

## Configuration

### mcp.json Format

Example configuration with GitHub MCP server:

```json
{
  "mcpServers": {
    "github": {
      "command": "npx",
      "args": [
        "-y",
        "@modelcontextprotocol/server-github"
      ],
      "env": {
        "GITHUB_PERSONAL_ACCESS_TOKEN": "your-token-here"
      },
      "transport": "stdio"
    }
  }
}
```

**Transport types:**
- **stdio**: Use `command` and `args` to start the server
- **http/sse**: Use `url` and optional `headers` for remote servers

## Usage

### Generate Code

**CLI:**
```bash
mcp2code generate --config .mcp/mcp.json --output _generated
```

**Python API:**
```python
from mcp2code import MCP2CodeGenerator

# From file
generator = MCP2CodeGenerator.from_file("mcp.json")

# From JSON string
generator = MCP2CodeGenerator.from_json(json_data)

# Generate
await generator.generate(output_dir="_generated")
```

### Use Generated Code

```python
from _generated import github__get_user, filesystem__read_file

async def main():
    user = await github__get_user(username="octocat")
    content = await filesystem__read_file(path="/tmp/test.txt")
```

### Close Connections (Optional)

```python
from _generated.runtime.connection_pool import ConnectionPool

pool = ConnectionPool.get_instance()
await pool.close_all()  # Connections auto-close on exit if not called
```

## Generated Structure

```
_generated/
├── __init__.py              # Export all tool functions
├── runtime/
│   └── connection_pool.py
├── github/                  # Server packages
│   ├── __init__.py
│   └── tools.py
└── filesystem/
    ├── __init__.py
    └── tools.py
```

## Notes

- Only tools with `outputSchema.type == "object"` are generated
- All functions are async
- Connections are lazy and shared per server
- Thread-safe for concurrent calls

## Tech Stack

Python 3.11+, MCP SDK, Pydantic, TypedDict
