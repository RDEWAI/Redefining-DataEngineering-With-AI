#!/bin/bash
# Run tests in the development environment

echo "Running tests in RDEWAI environment..."
docker-compose exec rdewai-dev pytest "$@"
