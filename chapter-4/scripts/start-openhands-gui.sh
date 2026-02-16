#!/bin/bash
# Start OpenHands GUI with PWI Integration
#
# This script:
# 1. Loads environment variables from .env
# 2. Builds and starts the OpenHands Docker container
# 3. Displays connection information
#
# Usage:
#   ./scripts/start-openhands-gui.sh
#
# Prerequisites:
#   - Docker and Docker Compose installed
#   - .env file with LLM_API_KEY configured

set -e

# Get script directory and project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_DIR"

# Export absolute paths for Docker volume mounts (required for nested sandbox containers)
# OpenHands creates sandbox containers that need host paths, not container paths
export WORKSPACE_HOST_PATH="$(pwd)"
export DATA_HOST_PATH="$(cd ../data && pwd)"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}========================================"
echo "PWI OpenHands GUI Launcher"
echo -e "========================================${NC}"
echo ""

# Check for Docker
if ! command -v docker &> /dev/null; then
    echo -e "${RED}Error: Docker is not installed${NC}"
    echo "Please install Docker from https://docker.com"
    exit 1
fi

# Check for Docker Compose
if ! docker compose version &> /dev/null && ! command -v docker-compose &> /dev/null; then
    echo -e "${RED}Error: Docker Compose is not installed${NC}"
    echo "Please install Docker Compose"
    exit 1
fi

# Load environment variables from .env if present
if [ -f .env ]; then
    echo -e "${GREEN}Loading environment from .env...${NC}"
    set -a
    source .env
    set +a
else
    echo -e "${YELLOW}Warning: No .env file found${NC}"
    echo "Create one with your LLM configuration:"
    echo "  echo 'LLM_API_KEY=your-key-here' > .env"
    echo "  echo 'LLM_BASE_URL=https://openrouter.ai/api/v1' >> .env"
    echo "  echo 'LLM_MODEL=openrouter/anthropic/claude-3.5-haiku' >> .env"
    echo ""
fi

# Validate required environment variables
if [ -z "$LLM_API_KEY" ]; then
    echo -e "${RED}Error: LLM_API_KEY is not set${NC}"
    echo "Set it in .env or export LLM_API_KEY=your-key"
    exit 1
fi

echo ""
echo "Configuration:"
echo "  Workspace: $PROJECT_DIR"
echo "  LLM Model: ${LLM_MODEL:-openrouter/anthropic/claude-3.5-haiku}"
echo "  Base URL:  ${LLM_BASE_URL:-https://openrouter.ai/api/v1}"
echo ""

# Determine compose command
COMPOSE_CMD="docker compose"
if ! docker compose version &> /dev/null; then
    COMPOSE_CMD="docker-compose"
fi

# Build and start
echo -e "${BLUE}Building and starting OpenHands GUI...${NC}"
echo ""

$COMPOSE_CMD -f docker-compose.openhands.yml up --build -d

# Wait for health check
echo ""
echo "Waiting for server to start..."
sleep 5

# Check if container is running
if docker ps | grep -q openhands-pwi; then
    echo ""
    echo -e "${GREEN}========================================"
    echo "OpenHands GUI is running!"
    echo -e "========================================${NC}"
    echo ""
    echo -e "Access the GUI at: ${BLUE}http://localhost:3000${NC}"
    echo ""
    echo "Available PWI Agents:"
    echo "  - data_analyst      Generate Data Requirements Documents (DRD)"
    echo "  - data_architect    Create Pipeline Architecture Documents (PAD)"
    echo "  - mapping_engineer  Build Data Mapping Documents (DMD)"
    echo "  - dq_engineer       Define Data Quality Specifications (DQS)"
    echo "  - story_writer      Write User Stories and Epics"
    echo "  - sync_agent        Create Consolidated Packages"
    echo "  - validator_agent   Validate Artifacts"
    echo ""
    echo "Example prompts to try:"
    echo "  \"Generate a DRD for the healthcare patient data\""
    echo "  \"List all tables in the DuckDB database\""
    echo "  \"Analyze the patients CSV file\""
    echo ""
    echo "To view logs:"
    echo "  docker logs -f openhands-pwi"
    echo ""
    echo "To stop:"
    echo "  $COMPOSE_CMD -f docker-compose.openhands.yml down"
    echo ""
else
    echo -e "${RED}Error: Container failed to start${NC}"
    echo "Check logs with: docker logs openhands-pwi"
    exit 1
fi
