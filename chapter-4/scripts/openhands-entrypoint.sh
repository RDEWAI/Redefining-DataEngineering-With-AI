#!/bin/bash
# OpenHands Entrypoint Script with PWI Tool Registration
#
# This script runs before the OpenHands server starts to:
# 1. Register all PWI custom tools with the OpenHands SDK
# 2. Verify microagent and skill discovery
# 3. Start the OpenHands server
#
# Usage: Called as ENTRYPOINT in Dockerfile.openhands

set -e

echo "========================================"
echo "PWI OpenHands Integration - Starting..."
echo "========================================"

# Add PWI to Python path
export PYTHONPATH="/app:/workspace:${PYTHONPATH}"

# Pre-import PWI tools to register them with OpenHands SDK
echo ""
echo "Registering PWI tools with OpenHands SDK..."
echo ""

python3 -c "
import sys
import os

# Ensure paths are set
sys.path.insert(0, '/app')
sys.path.insert(0, '/workspace')

print('Python path:', sys.path[:3])
print()

# Verify DuckDB is available
try:
    import duckdb
    print(f'  ✓ DuckDB version: {duckdb.__version__}')
except ImportError as e:
    print(f'  ⚠ DuckDB not available: {e}')

# Verify PWI tools are importable
try:
    from pwi.openhands.tools import duckdb_tool
    print('  ✓ PWI DuckDB tools available')
except ImportError as e:
    print(f'  ⚠ PWI tools not available: {e}')

# List microagent files
import glob
microagents = glob.glob('/app/.openhands/microagents/*.md')
print(f'  ✓ Found {len(microagents)} microagent definitions')

skills = glob.glob('/app/.openhands/skills/*.md')
print(f'  ✓ Found {len(skills)} skill definitions')

print()
print('PWI integration ready!')
"

echo ""
echo "========================================"
echo "Starting OpenHands Server..."
echo "========================================"
echo ""
echo "Access the GUI at: http://localhost:3000"
echo ""
echo "Available PWI Agents:"
echo "  - data_analyst: Generate Data Requirements Documents (DRD)"
echo "  - data_architect: Create Pipeline Architecture Documents (PAD)"
echo "  - mapping_engineer: Build Data Mapping Documents (DMD)"
echo "  - dq_engineer: Define Data Quality Specifications (DQS)"
echo "  - story_writer: Write User Stories and Epics"
echo "  - sync_agent: Create Consolidated Packages"
echo "  - validator_agent: Validate Artifacts"
echo ""
echo "========================================"
echo ""

# Execute the command passed to the entrypoint (default: uvicorn server)
exec "$@"
