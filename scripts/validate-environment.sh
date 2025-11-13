#!/usr/bin/env bash
# Environment Validation Script
# Checks for required prerequisites: UV, Python, Docker
#
# Exit Codes:
#   0: All prerequisites met
#   1: UV not found
#   2: Python version unsupported
#   3: Docker not found (only for raw-data-copy)
#   4: Docker daemon not running (only for raw-data-copy)

set -euo pipefail

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if UV is installed
check_uv() {
    if ! command -v uv &> /dev/null; then
        echo -e "${RED}ERROR: UV package manager not found.${NC}"
        echo ""
        echo "UV is required to manage Python dependencies for this project."
        echo ""
        echo "Install UV:"
        echo "  curl -LsSf https://astral.sh/uv/install.sh | sh"
        echo ""
        echo "After installation, restart your shell and try again."
        echo ""
        echo "For more information: https://docs.astral.sh/uv/"
        return 1
    fi
    echo -e "${GREEN}✓ UV found:${NC} $(uv --version)"
    return 0
}

# Check Python version (3.10, 3.11, or 3.12)
check_python() {
    if ! command -v python3 &> /dev/null; then
        echo -e "${RED}ERROR: Python 3 not found.${NC}"
        echo ""
        echo "This project requires Python 3.10, 3.11, or 3.12"
        echo ""
        echo "Install Python:"
        echo "  uv python install 3.12"
        echo ""
        echo "Or visit https://www.python.org/downloads/"
        return 2
    fi

    local python_version
    python_version=$(python3 --version 2>&1 | awk '{print $2}')
    local major minor
    major=$(echo "$python_version" | cut -d. -f1)
    minor=$(echo "$python_version" | cut -d. -f2)

    if [[ "$major" != "3" ]] || [[ "$minor" -lt 10 || "$minor" -gt 12 ]]; then
        echo -e "${RED}ERROR: Unsupported Python version detected.${NC}"
        echo ""
        echo "Current version: Python $python_version"
        echo "Required: Python 3.10, 3.11, or 3.12"
        echo ""
        echo "This project requires Python 3.10-3.12 due to Apache Superset compatibility."
        echo ""
        echo "Install compatible Python version:"
        echo "  uv python install 3.12"
        echo ""
        echo "Or visit https://www.python.org/downloads/"
        return 2
    fi

    echo -e "${GREEN}✓ Python version supported:${NC} $python_version"
    return 0
}

# Check if Docker is installed
check_docker() {
    if ! command -v docker &> /dev/null; then
        echo -e "${RED}ERROR: Docker not found.${NC}"
        echo ""
        echo "Docker is required to extract raw Synthea data from the container image."
        echo ""
        echo "Install Docker:"
        echo "  macOS: https://docs.docker.com/desktop/install/mac-install/"
        echo "  Linux: https://docs.docker.com/engine/install/"
        echo "  Windows: https://docs.docker.com/desktop/install/windows-install/"
        echo ""
        echo "After installation, start Docker and try again."
        return 3
    fi
    echo -e "${GREEN}✓ Docker found:${NC} $(docker --version)"
    return 0
}

# Check if Docker daemon is running
check_docker_daemon() {
    if ! docker info &> /dev/null; then
        echo -e "${RED}ERROR: Docker daemon is not running.${NC}"
        echo ""
        echo "Start Docker:"
        echo "  macOS/Windows: Open Docker Desktop"
        echo "  Linux: sudo systemctl start docker"
        echo ""
        echo "Then try again."
        return 4
    fi
    echo -e "${GREEN}✓ Docker daemon is running${NC}"
    return 0
}

# Main validation logic
main() {
    local check_type="${1:-all}"
    local exit_code=0

    echo "=== Environment Validation ==="
    echo ""

    case "$check_type" in
        uv)
            check_uv || exit_code=$?
            ;;
        python)
            check_python || exit_code=$?
            ;;
        docker)
            check_docker || exit_code=$?
            check_docker_daemon || exit_code=$?
            ;;
        dev-setup)
            check_uv || exit_code=$?
            check_python || exit_code=$?
            ;;
        raw-data)
            check_docker || exit_code=$?
            check_docker_daemon || exit_code=$?
            ;;
        all)
            check_uv || exit_code=$?
            check_python || exit_code=$?
            echo ""
            echo "Optional (for raw-data-copy):"
            check_docker || true
            check_docker_daemon || true
            ;;
        *)
            echo "Usage: $0 [uv|python|docker|dev-setup|raw-data|all]"
            exit 1
            ;;
    esac

    echo ""
    if [[ $exit_code -eq 0 ]]; then
        echo -e "${GREEN}=== All checks passed ===${NC}"
    else
        echo -e "${RED}=== Validation failed ===${NC}"
    fi

    return $exit_code
}

main "$@"
