"""Pytest configuration for chapter-2 tests.

This conftest ensures the external 'mcp' package is imported before
our src.mcp package to avoid import shadowing issues.
"""

from pathlib import Path

from dotenv import load_dotenv

# Load .env file from chapter-2 directory
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(env_path)

# Pre-import the external mcp package before any test imports
# This prevents our src/mcp directory from shadowing the external mcp package
import mcp.types  # noqa: F401, E402

import mcp  # noqa: F401, E402
