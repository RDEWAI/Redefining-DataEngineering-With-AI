#!/bin/bash
# Stop OpenHands GUI
#
# Usage:
#   ./scripts/stop-openhands-gui.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_DIR"

# Colors
GREEN='\033[0;32m'
NC='\033[0m'

# Determine compose command
COMPOSE_CMD="docker compose"
if ! docker compose version &> /dev/null; then
    COMPOSE_CMD="docker-compose"
fi

echo "Stopping OpenHands GUI..."
$COMPOSE_CMD -f docker-compose.openhands.yml down

echo -e "${GREEN}OpenHands GUI stopped.${NC}"
