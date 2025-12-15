#!/usr/bin/env python3
"""Quick test script for Phase 6 code execution.

This script demonstrates the code execution sandbox and tool API generator.
"""

import os

from src.code_execution.sandbox import CodeSandbox
from src.code_execution.tool_api import ToolAPIGenerator
from src.library.repository import BookRepository


def test_sandbox_basic():
    """Test basic sandbox execution."""
    print("=" * 60)
    print("TEST 1: Basic Sandbox Execution")
    print("=" * 60)

    sandbox = CodeSandbox()

    code = """
import pandas as pd
import numpy as np

# Simple calculation
data = [1, 2, 3, 4, 5]
mean = np.mean(data)
print(f"Mean: {mean}")

# Create DataFrame
df = pd.DataFrame({'values': data})
print(f"DataFrame shape: {df.shape}")
"""

    result = sandbox.execute(code)

    if result["success"]:
        print("✓ SUCCESS")
        print(f"Output:\n{result['stdout']}")
    else:
        print("✗ FAILED")
        print(f"Error:\n{result['stderr']}")

    print()


def test_sandbox_with_database():
    """Test sandbox with database access."""
    print("=" * 60)
    print("TEST 2: Sandbox with Database")
    print("=" * 60)

    db_path = os.getenv("DB_PATH", "data/duckdb/chapter3.db")

    if not os.path.exists(db_path):
        print(f"⚠ Skipping - database not found at {db_path}")
        print("  Run 'make load-data' first")
        print()
        return

    sandbox = CodeSandbox()

    code = f"""
import duckdb

conn = duckdb.connect('{db_path}', read_only=True)

# Query book count
count = conn.execute('SELECT COUNT(*) FROM library.books').fetchone()[0]
print(f"Total books: {{count}}")

# Query by category
categories = conn.execute('''
    SELECT category, COUNT(*) as count
    FROM library.books
    GROUP BY category
    ORDER BY count DESC
    LIMIT 3
''').fetchall()

print("\\nTop 3 categories:")
for cat, count in categories:
    print(f"  - {{cat}}: {{count}} books")
"""

    result = sandbox.execute(code)

    if result["success"]:
        print("✓ SUCCESS")
        print(f"Output:\n{result['stdout']}")
    else:
        print("✗ FAILED")
        print(f"Error:\n{result['stderr']}")

    print()


def test_tool_api_generator():
    """Test tool API code generation."""
    print("=" * 60)
    print("TEST 3: Tool API Generator")
    print("=" * 60)

    db_path = os.getenv("DB_PATH", "data/duckdb/chapter3.db")

    if not os.path.exists(db_path):
        print(f"⚠ Skipping - database not found at {db_path}")
        print("  Run 'make load-data' first")
        print()
        return

    # Create tool API generator
    repo = BookRepository(db_path=db_path)
    generator = ToolAPIGenerator(repo)

    # Show available functions
    print("Available API functions:")
    for name, desc in generator.get_tool_descriptions().items():
        print(f"  - {name}: {desc}")

    print("\n✓ SUCCESS - Tool API generated")
    print()


def test_code_execution_with_api():
    """Test executing code that uses the generated API."""
    print("=" * 60)
    print("TEST 4: Code Execution with Generated API")
    print("=" * 60)

    db_path = os.getenv("DB_PATH", "data/duckdb/chapter3.db")

    if not os.path.exists(db_path):
        print(f"⚠ Skipping - database not found at {db_path}")
        print("  Run 'make load-data' first")
        print()
        return

    # Generate API code
    repo = BookRepository(db_path=db_path)
    generator = ToolAPIGenerator(repo)
    api_code = generator.generate_api_code()

    # User code that uses the API
    user_code = """
# Search for Python books
python_books = search_books("Python", category="Programming")
print(f"Found {len(python_books)} Python programming books")

if python_books:
    first_book = python_books[0]
    print(f"\\nFirst book: {first_book['title']}")
    print(f"Author: {first_book['author']}")
    print(f"Status: {first_book['status']}")

# Check availability
if python_books:
    status = check_availability(python_books[0]['book_id'])
    print(f"\\nAvailability: {'Available' if status['available'] else 'Not available'}")
    if status['available']:
        print(f"Location: {status['location']}")
"""

    # Combine API + user code
    full_code = api_code + "\n" + user_code

    sandbox = CodeSandbox()
    result = sandbox.execute(full_code, db_path=db_path)

    if result["success"]:
        print("✓ SUCCESS")
        print(f"Output:\n{result['stdout']}")
    else:
        print("✗ FAILED")
        print(f"Error:\n{result['stderr']}")

    print()


def test_timeout():
    """Test timeout enforcement."""
    print("=" * 60)
    print("TEST 5: Timeout Enforcement")
    print("=" * 60)

    sandbox = CodeSandbox(timeout=2)  # 2 second timeout

    code = """
import time
print("Starting long operation...")
time.sleep(5)  # Will timeout
print("This won't print")
"""

    print("Executing code with 5 second sleep (2 second timeout)...")
    result = sandbox.execute(code)

    if result["timeout"]:
        print("✓ SUCCESS - Timeout enforced correctly")
        print(f"Error: {result['stderr']}")
    else:
        print("✗ FAILED - Timeout not enforced")

    print()


def main():
    """Run all tests."""
    print("\n" + "=" * 60)
    print("Phase 6: Code Execution Testing")
    print("=" * 60)
    print()

    # Run tests
    test_sandbox_basic()
    test_sandbox_with_database()
    test_tool_api_generator()
    test_code_execution_with_api()
    test_timeout()

    print("=" * 60)
    print("Testing Complete!")
    print("=" * 60)
    print("\nTo run the full benchmark:")
    print("  make benchmark")
    print("\nTo run unit tests:")
    print("  uv run pytest tests/unit/test_sandbox.py -v")
    print("\nTo run integration tests:")
    print("  uv run pytest tests/integration/test_code_execution.py -v")


if __name__ == "__main__":
    main()
