"""CLI for mcp2code"""

import asyncio
import logging
import sys
from pathlib import Path

import click

from mcp2code.generator import MCP2CodeGenerator

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@click.command(context_settings={"help_option_names": ["-h", "--help"]})
@click.option(
    "--config",
    "-c",
    type=click.Path(exists=True, path_type=Path),
    default=Path(".mcp/mcp.json"),
    help="Path to mcp.json configuration file (default: .mcp/mcp.json)",
)
@click.option(
    "--output",
    "-o",
    type=click.Path(path_type=Path),
    default=Path("_generated"),
    help="Output directory for generated code (default: _generated)",
)
@click.option(
    "--force",
    "-f",
    is_flag=True,
    help="Force overwrite existing files",
)
@click.option(
    "--verbose",
    "-v",
    is_flag=True,
    help="Enable verbose output",
)
def generate(config: Path, output: Path, force: bool, verbose: bool) -> None:
    """Generate Python packages from MCP configuration"""
    if verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    try:
        # Read config file
        with open(config, "r", encoding="utf-8") as f:
            json_data = f.read()

        # Create generator
        generator = MCP2CodeGenerator.from_json(json_data)

        # Generate code
        asyncio.run(generator.generate(output_dir=output, force=force))

        click.echo(f"✅ Generated code saved to {output}")
    except Exception as e:
        logger.error(f"Failed to generate code: {e}", exc_info=verbose)
        sys.exit(1)


if __name__ == "__main__":
    generate()
