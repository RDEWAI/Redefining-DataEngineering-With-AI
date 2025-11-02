#!/bin/bash
# Start development environment

echo "Starting RDEWAI development environment..."
docker-compose up -d

echo ""
echo "Development environment is ready!"
echo ""
echo "Available services:"
echo "  - Superset UI: http://localhost:8088"
echo "  - Spark UI: http://localhost:4040 (when running Spark jobs)"
echo ""
echo "To access the container:"
echo "  docker-compose exec rdewai-dev bash"
echo ""
echo "To stop the environment:"
echo "  docker-compose down"
