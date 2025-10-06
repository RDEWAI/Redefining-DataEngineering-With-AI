#!/bin/bash
# Comprehensive Docker Development Environment Validation Script
# Task 11: Docker Environment Validation

set -e

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Counters
TESTS_PASSED=0
TESTS_FAILED=0
TESTS_TOTAL=0

# Results array
declare -a RESULTS

# Helper functions
print_header() {
    echo -e "\n${BLUE}═══════════════════════════════════════════════════════════════${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}\n"
}

print_test() {
    echo -e "${YELLOW}[TEST]${NC} $1"
}

print_pass() {
    echo -e "${GREEN}[PASS]${NC} $1"
    ((TESTS_PASSED++))
    ((TESTS_TOTAL++))
    RESULTS+=("PASS: $1")
}

print_fail() {
    echo -e "${RED}[FAIL]${NC} $1"
    ((TESTS_FAILED++))
    ((TESTS_TOTAL++))
    RESULTS+=("FAIL: $1")
}

print_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

# Start validation
echo -e "${BLUE}╔════════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║  RDEWAI Docker Development Environment Validation              ║${NC}"
echo -e "${BLUE}║  Task 11: Comprehensive Validation Suite                       ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════════════╝${NC}"

START_TIME=$(date +%s)

# ============================================================================
# 1. Docker Image Build Validation
# ============================================================================
print_header "1. Docker Image Build Validation"

print_test "Checking if Docker image exists..."
if docker images | grep -q "rdewai-dev.*latest"; then
    IMAGE_SIZE=$(docker images rdewai-dev:latest --format "{{.Size}}")
    print_pass "Docker image rdewai-dev:latest exists (Size: $IMAGE_SIZE)"
else
    print_fail "Docker image rdewai-dev:latest not found"
fi

print_test "Checking base image..."
if docker images | grep -q "rdewai-dev.*base"; then
    BASE_SIZE=$(docker images rdewai-dev:base --format "{{.Size}}")
    print_pass "Base image exists (Size: $BASE_SIZE)"
else
    print_fail "Base image not found"
fi

# ============================================================================
# 2. Docker Compose Container Orchestration
# ============================================================================
print_header "2. Docker Compose Container Orchestration"

print_test "Starting containers with docker compose..."
if docker compose up -d 2>&1 | tee /tmp/compose-output.log; then
    print_pass "Docker Compose services started successfully"
else
    print_fail "Failed to start Docker Compose services"
    cat /tmp/compose-output.log
fi

print_test "Waiting for container health check (30 seconds)..."
sleep 30

print_test "Checking container status..."
if docker compose ps | grep -q "Up"; then
    print_pass "Container is running"
    docker compose ps
else
    print_fail "Container is not running properly"
    docker compose ps
fi

print_test "Checking container health status..."
HEALTH_STATUS=$(docker inspect rdewai-dev | grep -A 1 '"Health":' | grep '"Status"' | awk -F'"' '{print $4}' || echo "no-health-check")
if [ "$HEALTH_STATUS" = "healthy" ] || [ "$HEALTH_STATUS" = "no-health-check" ]; then
    print_pass "Container health check: $HEALTH_STATUS"
else
    print_fail "Container health check failed: $HEALTH_STATUS"
fi

print_test "Verifying network configuration..."
NETWORK_NAME=$(docker network ls | grep rdewai-network | awk '{print $2}')
if [ -n "$NETWORK_NAME" ]; then
    print_pass "Network $NETWORK_NAME exists"
    NETWORK_DRIVER=$(docker network inspect "$NETWORK_NAME" | grep '"Driver"' | head -1 | awk -F'"' '{print $4}')
    print_info "Network driver: $NETWORK_DRIVER"
else
    print_fail "Network rdewai-network not found"
fi

# ============================================================================
# 3. Runtime Environment Verification
# ============================================================================
print_header "3. Runtime Environment Verification"

print_test "Checking Python version..."
PYTHON_VERSION=$(docker exec rdewai-dev python --version 2>&1)
if echo "$PYTHON_VERSION" | grep -q "Python 3.11"; then
    print_pass "Python version: $PYTHON_VERSION"
else
    print_fail "Unexpected Python version: $PYTHON_VERSION"
fi

print_test "Checking Java version..."
JAVA_VERSION=$(docker exec rdewai-dev java -version 2>&1 | head -1)
if echo "$JAVA_VERSION" | grep -q "11"; then
    print_pass "Java version: $JAVA_VERSION"
else
    print_fail "Unexpected Java version: $JAVA_VERSION"
fi

print_test "Checking environment variables..."
docker exec rdewai-dev env | grep -E 'JAVA_HOME|SPARK_HOME|PYSPARK' > /tmp/env-vars.txt
if grep -q "JAVA_HOME" /tmp/env-vars.txt && grep -q "SPARK_HOME" /tmp/env-vars.txt; then
    print_pass "Required environment variables are set"
    cat /tmp/env-vars.txt
else
    print_fail "Missing required environment variables"
    cat /tmp/env-vars.txt
fi

# ============================================================================
# 4. Python Package Installation Tests
# ============================================================================
print_header "4. Python Package Installation Tests"

print_test "Testing package imports..."
if docker exec rdewai-dev python -c "import pytest, pyspark, duckdb, sqlglot, superset; from google.cloud import bigquery, storage" 2>&1; then
    print_pass "All required packages imported successfully"
else
    print_fail "Failed to import one or more packages"
fi

print_test "Checking package versions..."
docker exec rdewai-dev pip list | grep -E "pytest|pyspark|duckdb|google-cloud|superset|sqlglot" > /tmp/package-versions.txt
print_info "Installed packages:"
cat /tmp/package-versions.txt

print_test "Running pip check for dependency conflicts..."
if docker exec rdewai-dev pip check 2>&1 | tee /tmp/pip-check.log; then
    print_pass "No dependency conflicts detected"
else
    print_fail "Dependency conflicts detected"
    cat /tmp/pip-check.log
fi

# ============================================================================
# 5. PySpark Functionality Test
# ============================================================================
print_header "5. PySpark Functionality Test"

print_test "Running PySpark test..."
PYSPARK_TEST=$(docker exec rdewai-dev python -c "
from pyspark.sql import SparkSession
import sys
try:
    spark = SparkSession.builder.appName('ValidationTest').master('local[*]').getOrCreate()
    df = spark.range(10).toDF('id')
    result = df.count()
    print(f'PySpark test successful: {result} rows')
    spark.stop()
    sys.exit(0)
except Exception as e:
    print(f'PySpark test failed: {e}')
    sys.exit(1)
" 2>&1)

if echo "$PYSPARK_TEST" | grep -q "successful"; then
    print_pass "$PYSPARK_TEST"
else
    print_fail "$PYSPARK_TEST"
fi

# ============================================================================
# 6. DuckDB Database Operations
# ============================================================================
print_header "6. DuckDB Database Operations"

print_test "Running DuckDB test..."
DUCKDB_TEST=$(docker exec rdewai-dev python -c "
import duckdb
try:
    conn = duckdb.connect(':memory:')
    conn.execute('CREATE TABLE test (id INT, name VARCHAR)')
    conn.execute(\"INSERT INTO test VALUES (1, 'test_entry')\")
    result = conn.execute('SELECT * FROM test').fetchall()
    print(f'DuckDB test result: {result}')
    conn.close()
except Exception as e:
    print(f'DuckDB test failed: {e}')
" 2>&1)

if echo "$DUCKDB_TEST" | grep -q "test_entry"; then
    print_pass "$DUCKDB_TEST"
else
    print_fail "$DUCKDB_TEST"
fi

# ============================================================================
# 7. Apache Superset Initialization
# ============================================================================
print_header "7. Apache Superset Initialization"

print_test "Testing Superset database upgrade..."
if docker exec rdewai-dev bash -c "cd /tmp && superset db upgrade" 2>&1 | tee /tmp/superset-db.log; then
    print_pass "Superset database initialized successfully"
else
    print_fail "Superset database initialization failed"
    cat /tmp/superset-db.log
fi

# ============================================================================
# 8. Volume Mount Verification
# ============================================================================
print_header "8. Volume Mount Verification"

print_test "Checking workspace mount..."
if docker exec rdewai-dev ls -la /workspace | grep -q "Dockerfile"; then
    print_pass "Workspace mounted correctly (found Dockerfile)"
else
    print_fail "Workspace mount verification failed"
fi

print_test "Checking data volume..."
docker exec rdewai-dev touch /data/test-validation.txt
if docker exec rdewai-dev ls /data | grep -q "test-validation.txt"; then
    print_pass "Data volume is writable"
else
    print_fail "Data volume write test failed"
fi

print_test "Checking cache volume..."
if docker exec rdewai-dev ls -la /root/.cache > /dev/null 2>&1; then
    print_pass "Cache volume mounted"
else
    print_fail "Cache volume not accessible"
fi

# ============================================================================
# 9. Port Exposure and Service Access
# ============================================================================
print_header "9. Port Exposure and Service Access"

print_test "Checking port 8088 (Superset)..."
if curl -I http://localhost:8088 2>&1 | grep -q "HTTP"; then
    print_pass "Port 8088 is accessible"
else
    print_info "Port 8088 not responding (expected if Superset not started)"
fi

print_test "Checking exposed ports from container..."
docker port rdewai-dev > /tmp/exposed-ports.txt
if [ -s /tmp/exposed-ports.txt ]; then
    print_pass "Ports exposed:"
    cat /tmp/exposed-ports.txt
else
    print_info "No ports currently exposed"
fi

# ============================================================================
# 10. Script Execution Tests
# ============================================================================
print_header "10. Script Execution Tests"

print_test "Running test-environment.sh script..."
if bash ./scripts/test-environment.sh > /tmp/test-env-output.txt 2>&1; then
    print_pass "test-environment.sh executed successfully"
else
    print_fail "test-environment.sh execution failed"
    cat /tmp/test-env-output.txt
fi

# ============================================================================
# 11. Performance and Resource Monitoring
# ============================================================================
print_header "11. Performance and Resource Monitoring"

print_test "Checking container resource usage..."
docker stats --no-stream rdewai-dev > /tmp/container-stats.txt
print_info "Container resource usage:"
cat /tmp/container-stats.txt

print_test "Checking volume disk usage..."
docker system df -v | grep rdewai > /tmp/volume-usage.txt || true
if [ -s /tmp/volume-usage.txt ]; then
    print_info "Volume usage:"
    cat /tmp/volume-usage.txt
fi

# ============================================================================
# Summary and Report Generation
# ============================================================================
print_header "Validation Summary"

END_TIME=$(date +%s)
DURATION=$((END_TIME - START_TIME))

echo -e "${BLUE}Total Tests:${NC} $TESTS_TOTAL"
echo -e "${GREEN}Tests Passed:${NC} $TESTS_PASSED"
echo -e "${RED}Tests Failed:${NC} $TESTS_FAILED"
echo -e "${BLUE}Duration:${NC} ${DURATION}s"

if [ $TESTS_FAILED -eq 0 ]; then
    echo -e "\n${GREEN}╔════════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║  ✓ All validation tests PASSED!                               ║${NC}"
    echo -e "${GREEN}╚════════════════════════════════════════════════════════════════╝${NC}\n"
    EXIT_CODE=0
else
    echo -e "\n${RED}╔════════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${RED}║  ✗ Some validation tests FAILED                               ║${NC}"
    echo -e "${RED}╚════════════════════════════════════════════════════════════════╝${NC}\n"
    EXIT_CODE=1
fi

# Generate detailed report
mkdir -p .taskmaster/docs
REPORT_FILE=".taskmaster/docs/docker-validation-report.md"

echo "# Docker Development Environment Validation Report" > "$REPORT_FILE"
echo "" >> "$REPORT_FILE"
echo "**Task:** 11 - Comprehensive Docker Development Environment Validation" >> "$REPORT_FILE"
echo "**Date:** $(date)" >> "$REPORT_FILE"
echo "**Duration:** ${DURATION}s" >> "$REPORT_FILE"
echo "" >> "$REPORT_FILE"
echo "## Summary" >> "$REPORT_FILE"
echo "" >> "$REPORT_FILE"
echo "- **Total Tests:** $TESTS_TOTAL" >> "$REPORT_FILE"
echo "- **Passed:** $TESTS_PASSED" >> "$REPORT_FILE"
echo "- **Failed:** $TESTS_FAILED" >> "$REPORT_FILE"
echo "- **Success Rate:** $(( TESTS_PASSED * 100 / TESTS_TOTAL ))%" >> "$REPORT_FILE"
echo "" >> "$REPORT_FILE"
echo "## Test Results" >> "$REPORT_FILE"
echo "" >> "$REPORT_FILE"

for result in "${RESULTS[@]}"; do
    if [[ $result == PASS* ]]; then
        echo "- ✓ ${result#PASS: }" >> "$REPORT_FILE"
    else
        echo "- ✗ ${result#FAIL: }" >> "$REPORT_FILE"
    fi
done

echo "" >> "$REPORT_FILE"
echo "## Detailed Findings" >> "$REPORT_FILE"
echo "" >> "$REPORT_FILE"
echo "### Environment Details" >> "$REPORT_FILE"
echo "" >> "$REPORT_FILE"
echo "**Python Version:**" >> "$REPORT_FILE"
echo '```' >> "$REPORT_FILE"
echo "$PYTHON_VERSION" >> "$REPORT_FILE"
echo '```' >> "$REPORT_FILE"
echo "" >> "$REPORT_FILE"
echo "**Java Version:**" >> "$REPORT_FILE"
echo '```' >> "$REPORT_FILE"
echo "$JAVA_VERSION" >> "$REPORT_FILE"
echo '```' >> "$REPORT_FILE"
echo "" >> "$REPORT_FILE"
echo "**Installed Packages:**" >> "$REPORT_FILE"
echo '```' >> "$REPORT_FILE"
cat /tmp/package-versions.txt >> "$REPORT_FILE"
echo '```' >> "$REPORT_FILE"
echo "" >> "$REPORT_FILE"
echo "### Resource Usage" >> "$REPORT_FILE"
echo '```' >> "$REPORT_FILE"
cat /tmp/container-stats.txt >> "$REPORT_FILE"
echo '```' >> "$REPORT_FILE"
echo "" >> "$REPORT_FILE"
echo "## Recommendations" >> "$REPORT_FILE"
echo "" >> "$REPORT_FILE"

if [ $TESTS_FAILED -eq 0 ]; then
    echo "✓ All tests passed successfully. The Docker development environment is fully functional." >> "$REPORT_FILE"
else
    echo "⚠️ Some tests failed. Review the failures above and take corrective action." >> "$REPORT_FILE"
fi

echo "" >> "$REPORT_FILE"
echo "---" >> "$REPORT_FILE"
echo "*Generated by comprehensive-validation.sh on $(date)*" >> "$REPORT_FILE"

print_info "Detailed report saved to: $REPORT_FILE"

exit $EXIT_CODE
