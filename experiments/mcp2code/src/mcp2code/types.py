"""Type hint generation from JSON Schema"""

import re
from typing import Dict, Any, List


def should_skip_tool(tool: Dict[str, Any]) -> bool:
    """
    Check if tool should be skipped.

    Skip conditions:
    1. No outputSchema
    2. outputSchema is not JSON object (type != "object")
    """
    output_schema = tool.get("outputSchema")
    if not output_schema:
        return True  # Skip tools without outputSchema

    output_type = output_schema.get("type")
    if output_type != "object":
        return True  # Skip non-JSON object returns

    return False  # Support this tool


def sanitize_name(name: str) -> str:
    """Sanitize name for use in Python identifiers"""
    # Replace invalid characters with underscore
    name = re.sub(r"[^a-zA-Z0-9_]", "_", name)
    # Ensure it starts with letter or underscore
    if name and name[0].isdigit():
        name = "_" + name
    return name


def generate_type_hint(schema: Dict[str, Any], is_output: bool = False) -> str:
    """
    Recursively generate type hint from JSON Schema.

    Args:
        schema: JSON Schema
        is_output: Whether this is an output type (affects required field handling)

    Returns:
        Python type hint string
    """
    schema_type = schema.get("type")

    if schema_type == "string":
        return "str"
    elif schema_type == "integer":
        return "int"
    elif schema_type == "number":
        return "float"
    elif schema_type == "boolean":
        return "bool"
    elif schema_type == "array":
        items = schema.get("items", {})
        item_type = generate_type_hint(items, is_output) if items else "Any"
        return f"List[{item_type}]"
    elif schema_type == "object":
        # For objects, we'll generate TypedDict classes
        # Return a placeholder that will be replaced with class name
        class_name = schema.get("_class_name", "TypedDict")
        return class_name
    else:
        return "Any"


def generate_typed_dict(
    schema: Dict[str, Any],
    class_name: str,
    is_output: bool = False,
) -> str:
    """
    Generate TypedDict class definition from JSON Schema.

    Args:
        schema: JSON Schema object
        class_name: Name for the TypedDict class
        is_output: Whether this is an output type

    Returns:
        Python code for TypedDict class
    """
    properties = schema.get("properties", {})
    required = schema.get("required", [])

    if is_output:
        # Output type: required fields are mandatory
        base_class = "TypedDict"
    else:
        # Input type: use total=False
        base_class = "TypedDict, total=False"

    lines = [f"class {class_name}({base_class}):"]
    if not properties:
        lines.append('    """Empty TypedDict"""')
        lines.append("    pass")
    else:
        # Add docstring if available
        description = schema.get("description", "")
        if description:
            lines.append(f'    """{description}"""')

        # Generate field definitions
        for prop_name, prop_schema in properties.items():
            prop_type = generate_type_hint(prop_schema, is_output)
            is_required = prop_name in required

            # Generate field with comment if required (for input types)
            if is_required and not is_output:
                lines.append(f"    {prop_name}: {prop_type}  # required")
            else:
                lines.append(f"    {prop_name}: {prop_type}")

    return "\n".join(lines)


def generate_all_types(tools: List[Dict[str, Any]], server_name: str) -> tuple[str, Dict[str, str]]:
    """
    Generate all TypedDict classes for a server's tools.

    Args:
        tools: List of tool definitions
        server_name: Name of the server

    Returns:
        Tuple of (generated code, class_name_map)
        class_name_map maps tool_name to (input_class_name, output_class_name)
    """
    type_definitions = []
    class_name_map: Dict[str, tuple[str, str]] = {}

    for tool in tools:
        tool_name = tool["name"]
        sanitized_tool_name = sanitize_name(tool_name)
        server_prefix = sanitize_name(server_name)

        # Generate input type
        input_schema = tool.get("inputSchema", {})
        if input_schema and input_schema.get("type") == "object":
            input_class_name = f"{server_prefix}__{sanitized_tool_name}Input"
            input_class_name = sanitize_name(input_class_name)
            input_schema["_class_name"] = input_class_name
            type_definitions.append(
                generate_typed_dict(input_schema, input_class_name, is_output=False)
            )
        else:
            input_class_name = "Dict[str, Any]"

        # Generate output type
        output_schema = tool.get("outputSchema", {})
        if output_schema and output_schema.get("type") == "object":
            output_class_name = f"{server_prefix}__{sanitized_tool_name}Output"
            output_class_name = sanitize_name(output_class_name)
            output_schema["_class_name"] = output_class_name
            type_definitions.append(
                generate_typed_dict(output_schema, output_class_name, is_output=True)
            )
        else:
            output_class_name = "Dict[str, Any]"

        class_name_map[tool_name] = (input_class_name, output_class_name)

    return "\n\n".join(type_definitions), class_name_map


def generate_function_parameters(input_schema: Dict[str, Any]) -> tuple[str, str, str]:
    """
    Generate function parameters from input schema.

    Returns:
        Tuple of (parameter_string, arg_docs_string, arguments_dict_string)
    """
    properties = input_schema.get("properties", {})
    required = input_schema.get("required", [])

    if not properties:
        return "", "", "{}"

    params = []
    arg_docs = []
    args_dict_items = []

    for prop_name, prop_schema in properties.items():
        prop_type = generate_type_hint(prop_schema, is_output=False)
        prop_desc = prop_schema.get("description", f"Parameter for {prop_name}")

        if prop_name in required:
            params.append(f"{prop_name}: {prop_type}")
            arg_docs.append(f"        {prop_name}: {prop_desc}")
        else:
            params.append(f"{prop_name}: Optional[{prop_type}] = None")
            arg_docs.append(f"        {prop_name}: {prop_desc}")

        args_dict_items.append(f'        "{prop_name}": {prop_name}')

    param_str = ", ".join(params)
    arg_docs_str = "\n".join(arg_docs)
    args_dict_str = "{\n" + ",\n".join(args_dict_items) + "\n    }"

    return param_str, arg_docs_str, args_dict_str
