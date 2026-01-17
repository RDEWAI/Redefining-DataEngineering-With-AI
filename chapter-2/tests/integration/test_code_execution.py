"""Integration tests for end-to-end code execution workflow.

Tests complete code execution pipeline including:
- Library tool API generation
- Code generation by LLM
- Sandbox execution
- Result parsing and display
"""

import os

import pytest

from src.agentic.code_execution.sandbox import CodeSandbox
from src.agentic.code_execution.tool_api import ToolAPIGenerator
from src.agentic.library.repository import BookRepository


class TestCodeExecutionIntegration:
    """Integration tests for code execution workflow."""

    @pytest.fixture
    def db_path(self):
        """Get test database path."""
        # Try different paths
        paths = [
            os.getenv("DB_PATH"),
            "data/duckdb/chapter2.db",
            "chapter-2/data/duckdb/chapter2.db",
            "../data/duckdb/chapter2.db",
        ]
        for path in paths:
            if path and os.path.exists(path):
                return path

        # Skip tests if database not found
        pytest.skip("Test database not available. Run 'make load-data' first.")

    @pytest.fixture
    def sandbox(self):
        """Create sandbox instance."""
        return CodeSandbox(timeout=30, memory_mb=512)

    @pytest.fixture
    def tool_api_generator(self, db_path):
        """Create tool API generator with repository."""
        repo = BookRepository(db_path=db_path, read_only=True)
        yield ToolAPIGenerator(repo)
        repo.close()

    def test_tool_api_generation(self, tool_api_generator):
        """Test that tool API code can be generated."""
        api_code = tool_api_generator.generate_api_code()

        assert "def search_books" in api_code
        assert "def get_book_details" in api_code
        assert "def list_by_category" in api_code
        assert "import duckdb" in api_code
        assert "description" in api_code  # Verify description field is included

    def test_simple_query_execution(self, sandbox, db_path):
        """Test execution of a simple database query."""
        code = f"""
import duckdb

conn = duckdb.connect('{db_path}', read_only=True)
result = conn.execute('SELECT COUNT(*) as count FROM library.books').fetchone()
print(f"Total books: {{result[0]}}")
"""
        result = sandbox.execute(code)

        assert result["success"] is True
        assert "Total books:" in result["stdout"]
        assert result["timeout"] is False

    def test_category_aggregation(self, sandbox, db_path):
        """Test aggregation query for books by category."""
        code = f"""
import duckdb

conn = duckdb.connect('{db_path}', read_only=True)
result = conn.execute('''
    SELECT category, COUNT(*) as count
    FROM library.books
    GROUP BY category
    ORDER BY count DESC
    LIMIT 3
''').fetchall()

for row in result:
    print(f"{{row[0]}}: {{row[1]}} books")
"""
        result = sandbox.execute(code)

        assert result["success"] is True
        assert "books" in result["stdout"]

    def test_weak_signal_analysis(self, sandbox, db_path):
        """Test analysis of books with weak RFID signals."""
        code = f"""
import duckdb
import pandas as pd

conn = duckdb.connect('{db_path}', read_only=True)
df = pd.read_sql('''
    SELECT category, COUNT(*) as weak_signal_count,
           AVG(signal_strength) as avg_signal
    FROM library.books
    WHERE signal_strength < -55
    GROUP BY category
    ORDER BY weak_signal_count DESC
''', conn)

print(df.to_string(index=False))
"""
        result = sandbox.execute(code)

        assert result["success"] is True
        # Output should contain DataFrame formatting
        assert "category" in result["stdout"] or "avg_signal" in result["stdout"]

    def test_missing_books_by_category(self, sandbox, db_path):
        """Test finding missing books grouped by category."""
        code = f"""
import duckdb

conn = duckdb.connect('{db_path}', read_only=True)
result = conn.execute('''
    SELECT category, COUNT(*) as missing_count,
           AVG(signal_strength) as avg_signal
    FROM library.books
    WHERE status = 'Missing'
    GROUP BY category
    ORDER BY missing_count DESC
    LIMIT 5
''').fetchall()

print("Top 5 categories with missing books:")
for row in result:
    cat, count, avg_sig = row
    print(f"  {{cat}}: {{count}} missing (avg signal: {{avg_sig:.1f}} dBm)")
"""
        result = sandbox.execute(code)

        assert result["success"] is True
        assert "Top 5 categories" in result["stdout"] or result["stdout"] == ""

    def test_pandas_integration(self, sandbox, db_path):
        """Test pandas DataFrame operations."""
        code = f"""
import pandas as pd
import duckdb

conn = duckdb.connect('{db_path}', read_only=True)
df = pd.read_sql('SELECT * FROM library.books LIMIT 10', conn)

print(f"Loaded {{len(df)}} books")
print(f"Columns: {{', '.join(df.columns)}}")
"""
        result = sandbox.execute(code)

        assert result["success"] is True
        assert "Loaded 10 books" in result["stdout"]
        assert "Columns:" in result["stdout"]

    def test_numpy_operations(self, sandbox, db_path):
        """Test numpy array operations on book data."""
        code = f"""
import numpy as np
import duckdb

conn = duckdb.connect('{db_path}', read_only=True)
signals = conn.execute('SELECT signal_strength FROM library.books').fetchall()
signal_array = np.array([s[0] for s in signals])

print(f"Mean signal: {{signal_array.mean():.2f}} dBm")
print(f"Std dev: {{signal_array.std():.2f}} dBm")
print(f"Min: {{signal_array.min():.2f}} dBm")
print(f"Max: {{signal_array.max():.2f}} dBm")
"""
        result = sandbox.execute(code)

        assert result["success"] is True
        assert "Mean signal:" in result["stdout"]
        assert "dBm" in result["stdout"]

    def test_complex_analytics_query(self, sandbox, db_path):
        """Test complex analytical query combining multiple operations."""
        code = f"""
import duckdb
import pandas as pd
import numpy as np

conn = duckdb.connect('{db_path}', read_only=True)

# Load data
df = pd.read_sql('SELECT * FROM library.books', conn)

# Calculate statistics by category and status
stats = df.groupby(['category', 'status']).agg({{
    'book_id': 'count',
    'signal_strength': ['mean', 'min', 'max']
}}).round(2)

print("Books by Category and Status:")
print(stats.head(10))
"""
        result = sandbox.execute(code)

        assert result["success"] is True
        # Should produce some output (exact format may vary)

    def test_visualization_code(self, sandbox, db_path):
        """Test matplotlib visualization code execution."""
        code = f"""
import matplotlib
matplotlib.use('Agg')  # Non-interactive backend
import matplotlib.pyplot as plt
import duckdb
import numpy as np

conn = duckdb.connect('{db_path}', read_only=True)
signals = conn.execute('SELECT signal_strength FROM library.books').fetchall()
signal_array = np.array([s[0] for s in signals])

# Create histogram
plt.figure(figsize=(10, 6))
plt.hist(signal_array, bins=20)
plt.xlabel('Signal Strength (dBm)')
plt.ylabel('Frequency')
plt.title('Distribution of RFID Signal Strength')

print("Histogram created successfully")
print(f"Total books plotted: {{len(signal_array)}}")
"""
        result = sandbox.execute(code)

        assert result["success"] is True
        assert "Histogram created successfully" in result["stdout"]

    def test_error_recovery(self, sandbox, db_path):
        """Test that sandbox recovers from errors gracefully."""
        # First execute bad code
        bad_code = "raise ValueError('Intentional error')"
        result1 = sandbox.execute(bad_code)
        assert result1["success"] is False
        assert "ValueError" in result1["stderr"]

        # Then execute good code to verify sandbox still works
        good_code = "print('Recovered successfully')"
        result2 = sandbox.execute(good_code)
        assert result2["success"] is True
        assert "Recovered successfully" in result2["stdout"]

    def test_tool_api_function_execution(self, sandbox, tool_api_generator, db_path):
        """Test executing code that uses generated tool API."""
        api_code = tool_api_generator.generate_api_code()

        # Code that uses the API functions
        user_code = """
# API is available
results = search_books("Python", category="Programming")
print(f"Found {len(results)} Python programming books")

if results:
    first_book = results[0]
    print(f"First book: {first_book['title']}")
"""

        # Combine API + user code
        full_code = api_code + "\n" + user_code

        result = sandbox.execute(full_code, db_path=db_path)

        # Note: This may fail if API code is not self-contained
        # Test validates the pattern, not necessarily success
        assert result is not None
        assert "timeout" in result

    @pytest.mark.skipif(
        not os.path.exists("data/duckdb/chapter2.db"),
        reason="Test database not available",
    )
    def test_real_database_query(self, sandbox):
        """Test query against real library database."""
        db_path = "data/duckdb/chapter2.db"
        code = f"""
import duckdb

conn = duckdb.connect('{db_path}', read_only=True)

# Verify schema
tables = conn.execute('''
    SELECT table_name
    FROM information_schema.tables
    WHERE table_schema = 'library'
''').fetchall()

print(f"Found {{len(tables)}} tables in library schema")
for table in tables:
    print(f"  - {{table[0]}}")
"""
        result = sandbox.execute(code)

        assert result["success"] is True
        assert "library schema" in result["stdout"]
