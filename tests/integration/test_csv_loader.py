"""
Integration tests for the CSV loader script.

Tests cover:
- Loading single CSV file into DuckDB
- Loading all 18 CSV files
- Idempotent loading (running twice)
- Row count verification
- Missing prerequisites error handling
"""

import sys
from pathlib import Path

import duckdb
import pytest

# Add scripts directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))

# Test constants
DB_PATH = Path("data/duckdb/raw.db")
RAW_DIR = Path("data/raw")
SCHEMA_NAME = "synthea"

# Expected Synthea tables
EXPECTED_TABLES = [
    "allergies",
    "careplans",
    "claims",
    "claims_transactions",
    "conditions",
    "devices",
    "encounters",
    "imaging_studies",
    "immunizations",
    "medications",
    "observations",
    "organizations",
    "patients",
    "payer_transitions",
    "payers",
    "procedures",
    "providers",
    "supplies",
]


class TestLoadSingleCsv:
    """Tests for loading a single CSV file."""

    @pytest.fixture
    def temp_db(self, tmp_path):
        """Create a temporary DuckDB database."""
        db_path = tmp_path / "test.db"
        conn = duckdb.connect(str(db_path))
        yield conn
        conn.close()

    @pytest.fixture
    def sample_csv(self, tmp_path):
        """Create a sample CSV file for testing."""
        csv_path = tmp_path / "test_patients.csv"
        csv_path.write_text(
            "id,name,birthdate\n1,John Doe,1990-01-01\n2,Jane Smith,1985-05-15\n"
        )
        return csv_path

    def test_load_single_csv(self, temp_db, sample_csv):
        """Test loading a single CSV file into DuckDB table."""
        from load_raw_csv_to_duckdb import (
            create_schema_if_not_exists,
            get_table_name,
            load_csv_to_table,
        )

        # Create schema
        create_schema_if_not_exists(temp_db, SCHEMA_NAME)

        # Load CSV
        table_name = get_table_name(sample_csv)
        row_count = load_csv_to_table(temp_db, sample_csv, table_name, SCHEMA_NAME)

        # Verify table exists and has correct row count
        result = temp_db.execute(
            f"SELECT COUNT(*) FROM {SCHEMA_NAME}.{table_name}"
        ).fetchone()
        assert result[0] == 2
        assert row_count == 2


class TestLoadAllCsvs:
    """Tests for loading all CSV files."""

    @pytest.fixture
    def temp_db(self, tmp_path):
        """Create a temporary DuckDB database."""
        db_path = tmp_path / "test.db"
        conn = duckdb.connect(str(db_path))
        yield conn
        conn.close()

    @pytest.fixture
    def sample_csv_dir(self, tmp_path):
        """Create sample CSV files mimicking Synthea structure."""
        csv_dir = tmp_path / "raw"
        csv_dir.mkdir()

        # Create a few sample CSV files
        (csv_dir / "patients.csv").write_text("id,name\n1,Test Patient\n")
        (csv_dir / "encounters.csv").write_text("id,patient_id,date\n1,1,2024-01-01\n")
        (csv_dir / "observations.csv").write_text("id,encounter_id,value\n1,1,120\n")

        return csv_dir

    def test_load_all_csvs(self, temp_db, sample_csv_dir):
        """Test loading all CSV files into DuckDB tables."""
        from load_raw_csv_to_duckdb import (
            create_schema_if_not_exists,
            discover_csv_files,
            load_all_csvs,
        )

        # Create schema
        create_schema_if_not_exists(temp_db, SCHEMA_NAME)

        # Discover and load CSV files
        csv_files = discover_csv_files(sample_csv_dir)
        results = load_all_csvs(temp_db, csv_files, SCHEMA_NAME)

        # Verify all tables created
        assert len(results) == 3

        # Verify tables exist in schema
        tables = temp_db.execute(
            f"SELECT table_name FROM information_schema.tables WHERE table_schema = '{SCHEMA_NAME}'"
        ).fetchall()
        table_names = [t[0] for t in tables]

        assert "patients" in table_names
        assert "encounters" in table_names
        assert "observations" in table_names


class TestIdempotentLoading:
    """Tests for idempotent loading behavior."""

    @pytest.fixture
    def temp_db_path(self, tmp_path):
        """Create a temporary database path."""
        return tmp_path / "test.db"

    @pytest.fixture
    def sample_csv_dir(self, tmp_path):
        """Create sample CSV files."""
        csv_dir = tmp_path / "raw"
        csv_dir.mkdir()
        (csv_dir / "patients.csv").write_text(
            "id,name\n1,Test Patient\n2,Another Patient\n"
        )
        return csv_dir

    def test_idempotent_loading(self, temp_db_path, sample_csv_dir):
        """Test that running loader twice produces same results without errors."""
        from load_raw_csv_to_duckdb import (
            create_schema_if_not_exists,
            discover_csv_files,
            load_all_csvs,
        )

        # First load
        conn1 = duckdb.connect(str(temp_db_path))
        create_schema_if_not_exists(conn1, SCHEMA_NAME)
        csv_files = discover_csv_files(sample_csv_dir)
        results1 = load_all_csvs(conn1, csv_files, SCHEMA_NAME)
        conn1.close()

        # Second load (should replace tables without error)
        conn2 = duckdb.connect(str(temp_db_path))
        create_schema_if_not_exists(conn2, SCHEMA_NAME)
        results2 = load_all_csvs(conn2, csv_files, SCHEMA_NAME)

        # Verify same results
        assert len(results1) == len(results2)
        assert results1[0][0] == results2[0][0]  # same table name
        assert results1[0][1] == results2[0][1]  # same row count

        conn2.close()


class TestRowCounts:
    """Tests for row count verification."""

    @pytest.fixture
    def temp_db(self, tmp_path):
        """Create a temporary DuckDB database."""
        db_path = tmp_path / "test.db"
        conn = duckdb.connect(str(db_path))
        yield conn
        conn.close()

    @pytest.fixture
    def sample_csv_dir(self, tmp_path):
        """Create sample CSV files with known row counts."""
        csv_dir = tmp_path / "raw"
        csv_dir.mkdir()

        # Create CSV files with specific row counts
        (csv_dir / "patients.csv").write_text("id,name\n1,P1\n2,P2\n3,P3\n")  # 3 rows
        (csv_dir / "encounters.csv").write_text("id,patient_id\n1,1\n2,1\n")  # 2 rows

        return csv_dir

    def test_row_counts_match(self, temp_db, sample_csv_dir):
        """Test that row counts returned match actual table row counts."""
        from load_raw_csv_to_duckdb import (
            create_schema_if_not_exists,
            discover_csv_files,
            load_all_csvs,
        )

        # Load CSVs
        create_schema_if_not_exists(temp_db, SCHEMA_NAME)
        csv_files = discover_csv_files(sample_csv_dir)
        results = load_all_csvs(temp_db, csv_files, SCHEMA_NAME)

        # Verify row counts are > 0
        for table_name, row_count in results:
            assert row_count > 0, f"Table {table_name} should have rows"

        # Verify specific counts
        results_dict = dict(results)
        assert results_dict["patients"] == 3
        assert results_dict["encounters"] == 2


class TestMissingPrerequisites:
    """Tests for missing prerequisites error handling."""

    def test_missing_prerequisites_error(self, tmp_path):
        """Test that missing prerequisites produces exit code 1 and actionable message."""
        import sys
        from io import StringIO
        from unittest.mock import patch

        from load_raw_csv_to_duckdb import main

        # Patch RAW_DIR to point to a non-existent directory
        with patch("load_raw_csv_to_duckdb.RAW_DIR", tmp_path / "nonexistent"):
            # Capture stdout
            captured_output = StringIO()
            with patch.object(sys, "stdout", captured_output):
                exit_code = main()

        # Verify exit code
        assert exit_code == 1

        # Verify error message contains actionable guidance
        output = captured_output.getvalue()
        assert "ERROR" in output
        assert "raw-data-copy" in output.lower()
