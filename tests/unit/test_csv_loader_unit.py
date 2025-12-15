"""
Unit tests for the CSV loader script.

Tests cover:
- Table name extraction from CSV filenames
- CSV file discovery logic
- Prerequisite validation
- Progress output formatting
"""

import sys
from pathlib import Path

import pytest

# Add scripts directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))


class TestGetTableName:
    """Tests for get_table_name() function."""

    def test_get_table_name_patients(self):
        """Test extracting table name from patients.csv."""
        from load_raw_csv_to_duckdb import get_table_name

        result = get_table_name(Path("data/raw/patients.csv"))
        assert result == "patients"

    def test_get_table_name_claims_transactions(self):
        """Test extracting table name with underscore."""
        from load_raw_csv_to_duckdb import get_table_name

        result = get_table_name(Path("data/raw/claims_transactions.csv"))
        assert result == "claims_transactions"

    def test_get_table_name_absolute_path(self):
        """Test with absolute path."""
        from load_raw_csv_to_duckdb import get_table_name

        result = get_table_name(Path("/some/absolute/path/encounters.csv"))
        assert result == "encounters"


class TestDiscoverCsvFiles:
    """Tests for discover_csv_files() function."""

    def test_discover_csv_files_finds_files(self, tmp_path):
        """Test discovering CSV files in a directory."""
        from load_raw_csv_to_duckdb import discover_csv_files

        # Create test CSV files
        (tmp_path / "patients.csv").write_text("id,name\n1,Test")
        (tmp_path / "encounters.csv").write_text("id,date\n1,2024-01-01")
        (tmp_path / "not_csv.txt").write_text("ignore me")

        result = discover_csv_files(tmp_path)

        assert len(result) == 2
        assert result[0].name == "encounters.csv"  # sorted alphabetically
        assert result[1].name == "patients.csv"

    def test_discover_csv_files_empty_dir(self, tmp_path):
        """Test with empty directory returns empty list."""
        from load_raw_csv_to_duckdb import discover_csv_files

        result = discover_csv_files(tmp_path)
        assert result == []

    def test_discover_csv_files_missing_dir(self):
        """Test with non-existent directory raises error."""
        from load_raw_csv_to_duckdb import discover_csv_files

        with pytest.raises(FileNotFoundError):
            discover_csv_files(Path("/nonexistent/path"))


class TestProgressOutput:
    """Tests for progress output formatting."""

    def test_progress_output_format(self, tmp_path, capsys):
        """Test that progress messages follow [N/total] Loading table... format."""
        import duckdb

        from load_raw_csv_to_duckdb import (
            create_schema_if_not_exists,
            discover_csv_files,
            load_all_csvs,
        )

        # Create test CSV files
        csv_dir = tmp_path / "raw"
        csv_dir.mkdir()
        (csv_dir / "patients.csv").write_text("id,name\n1,Test\n")
        (csv_dir / "encounters.csv").write_text("id,date\n1,2024-01-01\n")

        # Load and capture output
        db_path = tmp_path / "test.db"
        conn = duckdb.connect(str(db_path))
        create_schema_if_not_exists(conn, "test_schema")
        csv_files = discover_csv_files(csv_dir)
        load_all_csvs(conn, csv_files, "test_schema")
        conn.close()

        # Verify output format
        captured = capsys.readouterr()
        assert "[1/2] Loading encounters..." in captured.out
        assert "[2/2] Loading patients..." in captured.out
        assert "✓ Loaded" in captured.out
        assert "rows" in captured.out

    def test_summary_output_format(self, tmp_path, capsys):
        """Test that summary includes total tables, total rows, and elapsed time."""
        from load_raw_csv_to_duckdb import print_summary

        # Test results
        results = [("patients", 100), ("encounters", 250), ("observations", 1000)]
        elapsed = 5.25

        # Print summary and capture
        print_summary(results, elapsed)
        captured = capsys.readouterr()

        # Verify summary content
        assert "3" in captured.out  # total tables
        assert "1,350" in captured.out  # total rows (100 + 250 + 1000)
        assert "5.25" in captured.out or "5.2" in captured.out  # elapsed time


class TestValidatePrerequisites:
    """Tests for validate_prerequisites() function."""

    def test_validate_prerequisites_success(self, tmp_path):
        """Test that validation passes with valid directory containing CSV files."""
        from load_raw_csv_to_duckdb import validate_prerequisites

        # Create valid directory structure
        raw_dir = tmp_path / "raw"
        raw_dir.mkdir()
        (raw_dir / "patients.csv").write_text("id,name\n1,Test\n")

        # Should not raise any exception
        validate_prerequisites(raw_dir)

    def test_validate_prerequisites_missing_raw_dir(self, tmp_path):
        """Test that validation fails when raw directory doesn't exist."""
        from load_raw_csv_to_duckdb import PrerequisiteError, validate_prerequisites

        # Non-existent directory
        raw_dir = tmp_path / "nonexistent"

        with pytest.raises(PrerequisiteError) as exc_info:
            validate_prerequisites(raw_dir)

        assert "not found" in str(exc_info.value).lower()
        assert "raw-data-copy" in str(exc_info.value).lower()

    def test_validate_prerequisites_no_csv_files(self, tmp_path):
        """Test that validation fails when directory has no CSV files."""
        from load_raw_csv_to_duckdb import PrerequisiteError, validate_prerequisites

        # Create empty directory
        raw_dir = tmp_path / "raw"
        raw_dir.mkdir()

        with pytest.raises(PrerequisiteError) as exc_info:
            validate_prerequisites(raw_dir)

        assert "no csv" in str(exc_info.value).lower()
        assert "raw-data-copy" in str(exc_info.value).lower()
