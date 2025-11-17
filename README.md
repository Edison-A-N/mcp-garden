# MCP-Garden 🌱

> **Model Context Protocol (MCP) Experimental Garden** - The most developer-friendly experimental playground for MCP implementations

[![Version](https://img.shields.io/badge/version-v0.1-blue.svg)](https://github.com/your-username/mcp-garden)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

## 🎯 Mission

**MCP-Garden** is the most developer-friendly experimental garden for Model Context Protocol implementations. We provide **runnable, comparable, and reusable** experimental projects for servers, clients, and LLM integrations, lowering the barrier for developers to get started and innovate.

## 🚀 Quick Start

### What is MCP?

**Model Context Protocol (MCP)** is an open standard for connecting AI assistants with data sources and tools. It enables secure access to external data sources, execution of operations, and integration with various services.

## 🧪 Experiments

#### [mcp2code](experiments/mcp2code/)
A tool that automatically generates Python packages from `mcp.json` configuration files. Each MCP server corresponds to an independent Python package, and each tool corresponds to an async function.

**Key Features:**
- Generate independent Python packages for each MCP server
- Lazy connections with global connection pool
- Auto-generated type hints from JSON schemas
- Support for stdio and HTTP/SSE transports

#### [FastAPI MCP SDK](experiments/fastapi-mcp-sdk/)
A streamlined SDK for converting FastAPI applications to MCP servers using FastMCP's experimental OpenAPI parser.

**Key Features:**
- Convert FastAPI endpoints to MCP tools automatically
- Support both separate and integrated server modes

## 📖 Resources

- [MCP Official Docs](https://modelcontextprotocol.io/)
- [MCP Specification](https://spec.modelcontextprotocol.io/)
- [Awesome MCP](./awesome-mcp/) - Curated list of MCP projects, tools, and resources

## 📄 License

MIT License - see [LICENSE](LICENSE) for details.
