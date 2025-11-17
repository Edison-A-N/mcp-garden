"""MCP client code generator"""

import json
import logging
from pathlib import Path
from typing import Dict, Any, List

from mcp2code.config import MCPConfig, MCPServerConfig
from mcp2code.transport import discover_tools_from_server
from mcp2code.types import (
    should_skip_tool,
    sanitize_name,
    generate_all_types,
    generate_function_parameters,
)

logger = logging.getLogger(__name__)


class MCP2CodeGenerator:
    """Generate Python packages from MCP configuration"""

    def __init__(self, config: MCPConfig):
        """
        Initialize the generator.

        Args:
            config: MCPConfig object
        """
        self.config = config
        self.discovered_tools: Dict[str, List[Dict[str, Any]]] = {}

    @classmethod
    def from_file(cls, config_path: str) -> "MCP2CodeGenerator":
        """Create generator from file path"""
        config = MCPConfig.from_file(config_path)
        return cls(config)

    @classmethod
    def from_json(cls, json_data: str) -> "MCP2CodeGenerator":
        """Create generator from JSON string"""
        config = MCPConfig.from_json(json_data)
        return cls(config)

    @classmethod
    def from_dict(cls, config_dict: Dict[str, Any]) -> "MCP2CodeGenerator":
        """Create generator from dictionary"""
        config = MCPConfig.from_dict(config_dict)
        return cls(config)

    async def discover_all_tools(self) -> Dict[str, List[Dict[str, Any]]]:
        """Discover all tools from configured MCP servers"""
        discovered_tools = {}

        for server_name, server_config in self.config.mcpServers.items():
            try:
                tools = await discover_tools_from_server(server_name, server_config)
                # Filter tools: only keep those with outputSchema
                supported_tools = []
                skipped_count = 0
                for tool in tools:
                    if should_skip_tool(tool):
                        skipped_count += 1
                        logger.warning(
                            f"Skipping tool '{tool['name']}' from server '{server_name}': "
                            "no outputSchema or non-JSON return type"
                        )
                    else:
                        supported_tools.append(tool)

                discovered_tools[server_name] = supported_tools
                if len(supported_tools) > 0:
                    logger.info(
                        f"Discovered {len(supported_tools)} supported tools from server '{server_name}'"
                        + (f" (skipped {skipped_count})" if skipped_count > 0 else "")
                    )
                else:
                    logger.warning(
                        f"No supported tools found for server '{server_name}'"
                        + (f" (all {skipped_count} tools skipped)" if skipped_count > 0 else "")
                    )
            except Exception as e:
                logger.error(
                    f"Failed to discover tools from server '{server_name}': {e}",
                    exc_info=logger.isEnabledFor(logging.DEBUG),
                )
                discovered_tools[server_name] = []

        self.discovered_tools = discovered_tools
        return discovered_tools

    async def generate(self, output_dir: str | Path, force: bool = False) -> None:
        """
        Generate Python packages.

        Args:
            output_dir: Output directory for generated code
            force: Force overwrite existing files
        """
        if not self.discovered_tools:
            await self.discover_all_tools()

        output_path = Path(output_dir)
        if output_path.exists() and not force:
            raise FileExistsError(
                f"Output directory '{output_dir}' already exists. Use --force to overwrite."
            )

        # Create output directory
        output_path.mkdir(parents=True, exist_ok=True)

        # Generate runtime support
        self._generate_runtime(output_path)

        # Generate packages for each server
        all_exports = []
        for server_name, tools in self.discovered_tools.items():
            if not tools:
                logger.warning(
                    f"No supported tools for server '{server_name}', skipping package generation"
                )
                continue

            exports = self._generate_server_package(server_name, tools, output_path)
            all_exports.extend(exports)

        # Generate root __init__.py
        self._generate_root_init(output_path, all_exports)

        logger.info(f"Generated code saved to {output_path}")

    def _generate_runtime(self, output_dir: Path) -> None:
        """Generate runtime support files"""
        runtime_dir = output_dir / "runtime"
        runtime_dir.mkdir(exist_ok=True)

        # Copy connection_pool.py
        # Read the source file
        source_file = Path(__file__).parent / "runtime" / "connection_pool.py"
        target_file = runtime_dir / "connection_pool.py"

        with open(source_file, "r", encoding="utf-8") as f:
            content = f.read()

        # Write to target
        with open(target_file, "w", encoding="utf-8") as f:
            f.write(content)

        # Generate runtime __init__.py
        init_file = runtime_dir / "__init__.py"
        with open(init_file, "w", encoding="utf-8") as f:
            f.write('"""Runtime support for generated MCP client packages"""\n\n')
            f.write("from runtime.connection_pool import ConnectionPool\n\n")
            f.write('__all__ = ["ConnectionPool"]\n')

    def _generate_server_package(
        self, server_name: str, tools: List[Dict[str, Any]], output_dir: Path
    ) -> List[str]:
        """Generate package for a single server"""
        server_dir = output_dir / sanitize_name(server_name)
        server_dir.mkdir(exist_ok=True)

        # Generate types
        type_code, class_name_map = generate_all_types(tools, server_name)

        # Generate tools.py
        tools_code = self._generate_tools_file(server_name, tools, type_code, class_name_map)
        tools_file = server_dir / "tools.py"
        with open(tools_file, "w", encoding="utf-8") as f:
            f.write(tools_code)

        # Generate __init__.py
        exports = self._generate_server_init(server_name, tools, server_dir, class_name_map)

        return exports

    def _generate_tools_file(
        self,
        server_name: str,
        tools: List[Dict[str, Any]],
        type_code: str,
        class_name_map: Dict[str, tuple[str, str]],
    ) -> str:
        """Generate tools.py file"""

        lines = [
            f'"""Auto-generated tool functions for {server_name} server"""',
            "",
            "import json",
            "from typing import TypedDict, Dict, Any, Optional, List",
            "from runtime.connection_pool import ConnectionPool",
            "",
        ]

        # Add type definitions
        if type_code:
            lines.append(type_code)
            lines.append("")

        # Generate tool functions
        for tool in tools:
            tool_name = tool["name"]
            function_code = self._generate_tool_function(
                server_name,
                tool,
                class_name_map.get(tool_name, ("Dict[str, Any]", "Dict[str, Any]")),
            )
            lines.append(function_code)
            lines.append("")

        return "\n".join(lines)

    def _generate_tool_function(
        self,
        server_name: str,
        tool: Dict[str, Any],
        class_names: tuple[str, str],
    ) -> str:
        """Generate a single tool function"""
        tool_name = tool["name"]
        description = tool.get("description", "")
        input_schema = tool.get("inputSchema", {})
        output_class_name = class_names[1]

        # Generate function name
        server_sanitized = sanitize_name(server_name)
        tool_sanitized = sanitize_name(tool_name)
        function_name = f"{server_sanitized}__{tool_sanitized}"

        # Generate parameters
        param_str, arg_docs_str, args_dict_str = generate_function_parameters(input_schema)

        # Generate docstring
        docstring_lines = [
            f'    """{description}',
            "",
            "    Args:",
        ]
        if arg_docs_str:
            docstring_lines.append(arg_docs_str)
        else:
            docstring_lines.append("        None")
        docstring_lines.extend(
            [
                "",
                "    Returns:",
                f"        {output_class_name}: Tool execution result",
                '    """',
            ]
        )

        # Generate function body
        if param_str:
            func_signature = f"async def {function_name}({param_str}) -> {output_class_name}:"
        else:
            func_signature = f"async def {function_name}() -> {output_class_name}:"

        function_lines = [func_signature]
        function_lines.extend(docstring_lines)
        function_lines.extend(
            [
                "    pool = ConnectionPool.get_instance()",
                f'    session = await pool.get_session("{server_name}")',
                "    ",
            ]
        )

        if args_dict_str and args_dict_str != "{}":
            function_lines.extend(
                [
                    f"    arguments = {args_dict_str}",
                    "    ",
                    "    # Filter out None values from arguments",
                    "    arguments = {k: v for k, v in arguments.items() if v is not None}",
                ]
            )
        else:
            function_lines.append("    arguments = {}")

        function_lines.extend(
            [
                "    ",
                f'    result = await session.call_tool("{tool_name}", arguments)',
                "    ",
                "    # Extract and return JSON result",
                "    # Priority: structuredContent > content",
                "    if hasattr(result, 'structuredContent') and result.structuredContent:",
                "        return result.structuredContent",
                "    if hasattr(result, 'content') and result.content:",
                "        import json",
                "        content_text = result.content[0].text if hasattr(result.content[0], 'text') else str(result.content[0])",
                "        try:",
                "            return json.loads(content_text)",
                "        except json.JSONDecodeError:",
                "            return content_text",
                "    return result",
            ]
        )

        return "\n".join(function_lines)

    def _generate_server_init(
        self,
        server_name: str,
        tools: List[Dict[str, Any]],
        server_dir: Path,
        class_name_map: Dict[str, tuple[str, str]],
    ) -> List[str]:
        """Generate server package __init__.py"""
        server_sanitized = sanitize_name(server_name)
        server_config = self.config.mcpServers[server_name]

        # Generate exports
        exports = []
        for tool in tools:
            tool_name = tool["name"]
            tool_sanitized = sanitize_name(tool_name)
            function_name = f"{server_sanitized}__{tool_sanitized}"
            exports.append(function_name)

        # Generate config dict
        config_dict = self._generate_config_dict(server_name, server_config)

        # Generate __init__.py content
        lines = [
            f'"""Auto-generated MCP client package for {server_name} server"""',
            "",
            "from runtime.connection_pool import ConnectionPool",
            "from .tools import (",
        ]

        # Add imports
        for export in exports:
            lines.append(f"    {export},")

        lines.extend(
            [
                ")",
                "",
                "# Register server configuration",
                "# Note: Generated code requires mcp2code package for MCPServerConfig",
                f"_config_dict = {config_dict}",
                "",
                "def _register_config():",
                "    try:",
                "        from mcp2code.config import MCPServerConfig",
                "        pool = ConnectionPool.get_instance()",
                f'        pool.register_config("{server_name}", MCPServerConfig(**_config_dict))',
                "    except ImportError:",
                "        import warnings",
                '        warnings.warn("mcp2code package not found. Install it to use generated code.")',
                "",
                "# Auto-register on import",
                "_register_config()",
                "",
                "__all__ = [",
            ]
        )

        for export in exports:
            lines.append(f'    "{export}",')

        lines.append("]")

        init_file = server_dir / "__init__.py"
        with open(init_file, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))

        return exports

    def _generate_config_dict(self, server_name: str, config: MCPServerConfig) -> str:
        """Generate config dictionary for registration"""
        config_dict = {}
        if config.command:
            config_dict["command"] = config.command
        if config.args:
            config_dict["args"] = config.args
        if config.env:
            config_dict["env"] = config.env
        if config.url:
            config_dict["url"] = config.url
        if config.transport:
            config_dict["transport"] = config.transport
        if config.headers:
            config_dict["headers"] = config.headers

        return json.dumps(config_dict, indent=4)

    def _generate_root_init(self, output_dir: Path, all_exports: List[str]) -> None:
        """Generate root __init__.py"""
        if not all_exports:
            # No exports, create empty __init__.py
            init_file = output_dir / "__init__.py"
            with open(init_file, "w", encoding="utf-8") as f:
                f.write('"""Auto-generated MCP client packages"""\n\n__all__ = []\n')
            return

        lines = [
            '"""Auto-generated MCP client packages"""',
            "",
        ]

        # Group exports by server
        server_exports: Dict[str, List[str]] = {}
        for export in all_exports:
            parts = export.split("__", 1)
            if len(parts) == 2:
                server_name = parts[0]
                if server_name not in server_exports:
                    server_exports[server_name] = []
                server_exports[server_name].append(export)

        # Generate imports
        for server_name, exports in server_exports.items():
            lines.append(f"from {server_name} import (")
            for export in exports:
                lines.append(f"    {export},")
            lines.append(")")
            lines.append("")

        lines.extend(
            [
                "__all__ = [",
            ]
        )

        for export in all_exports:
            lines.append(f'    "{export}",')

        lines.append("]")

        init_file = output_dir / "__init__.py"
        with open(init_file, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
