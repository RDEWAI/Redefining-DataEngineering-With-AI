"""Tests for the implementation sequence generator script."""

from __future__ import annotations

import sys
from pathlib import Path

# Add the generator's parent directory to sys.path
GENERATOR_DIR = (
    Path(__file__).resolve().parent.parent
    / "technical-lead-plugin"
    / "skills"
    / "create-lld"
    / "scripts"
)
sys.path.insert(0, str(GENERATOR_DIR))

from generate_impl_sequence import (  # noqa: E402
    build_phases,
    classify_module_layer,
    extract_title,
    generate_impl_sequence,
    parse_code_tree,
    parse_sections,
)

SAMPLE_LLD = """\
# Low-Level Design: Test Pipeline

## 1. Design Overview

Test overview.

## 2. Code Architecture

### 2.1 Project Structure

```
test-pipeline/
+-- src/
|   +-- config/
|   |   +-- __init__.py
|   |   +-- settings.py              # Config model
|   +-- pipelines/
|   |   +-- bronze/
|   |   |   +-- __init__.py
|   |   |   +-- ingest_a.py
|   |   +-- silver/
|   |   |   +-- __init__.py
|   |   |   +-- transform_a.py       # SCD2
|   |   +-- gold/
|   |   |   +-- __init__.py
|   |   |   +-- build_summary.py
|   +-- transforms/
|   |   +-- __init__.py
|   |   +-- scd2.py                   # Delta MERGE
+-- dags/
|   +-- pipeline_v1.py                # Airflow DAG
```

## 4. DAG Specification

### 4.2 Task Inventory

| Task ID | Type | Layer | Dependencies |
|---------|------|-------|-------------|
| `ingest_a` | PySpark | Bronze | None |
| `transform_a` | PySpark | Silver | `ingest_a` |
| `build_summary` | PySpark | Gold | `transform_a` |

## 9. Deployment

Deployment to DEV, STAGING, PROD.

## 12. Traceability Matrix

### 12.1 Functional Requirements

| Requirement | DRD Ref | Implementation Component | LLD Section |
|-------------|---------|-------------------------|-------------|
| FR-1: Summary | DRD §1.1 | `build_summary` | §5.3 |
"""


class TestExtractTitle:
    def test_extracts_title(self):
        title = extract_title(SAMPLE_LLD)
        assert "Test Pipeline" in title


class TestParseCodeTree:
    def test_parses_modules(self):
        sections = parse_sections(SAMPLE_LLD)
        modules = parse_code_tree(sections["2. Code Architecture"])
        paths = [m["path"] for m in modules]
        assert any("settings.py" in p for p in paths)
        assert any("ingest_a.py" in p for p in paths)
        assert any("scd2.py" in p for p in paths)

    def test_preserves_directory_paths(self):
        sections = parse_sections(SAMPLE_LLD)
        modules = parse_code_tree(sections["2. Code Architecture"])
        paths = [m["path"] for m in modules]
        # Should have directory context
        bronze_paths = [p for p in paths if "bronze" in p]
        assert len(bronze_paths) > 0

    def test_extracts_comments(self):
        sections = parse_sections(SAMPLE_LLD)
        modules = parse_code_tree(sections["2. Code Architecture"])
        scd2_mod = [m for m in modules if "scd2" in m["path"]]
        assert len(scd2_mod) == 1
        assert "Delta MERGE" in scd2_mod[0]["comment"]

    def test_skips_init_files(self):
        sections = parse_sections(SAMPLE_LLD)
        modules = parse_code_tree(sections["2. Code Architecture"])
        init_mods = [m for m in modules if "__init__" in m["path"]]
        assert len(init_mods) == 0


class TestClassifyModuleLayer:
    def test_config_is_foundation(self):
        assert classify_module_layer("src/config/settings.py") == "foundation"

    def test_utils_is_foundation(self):
        assert classify_module_layer("src/utils/logging.py") == "foundation"

    def test_transforms_is_shared(self):
        assert classify_module_layer("src/transforms/scd2.py") == "shared"

    def test_bronze_is_bronze(self):
        assert classify_module_layer("src/pipelines/bronze/ingest_a.py") == "bronze"

    def test_silver_is_silver(self):
        assert classify_module_layer("src/pipelines/silver/transform_a.py") == "silver"

    def test_gold_is_gold(self):
        assert classify_module_layer("src/pipelines/gold/build_summary.py") == "gold"

    def test_dags_is_orchestration(self):
        assert classify_module_layer("dags/pipeline_v1.py") == "orchestration"


class TestBuildPhases:
    def test_creates_phases(self):
        modules = [
            {"path": "src/config/settings.py", "comment": ""},
            {"path": "src/pipelines/bronze/ingest_a.py", "comment": ""},
            {"path": "src/pipelines/gold/build_summary.py", "comment": ""},
        ]
        phases = build_phases(modules)
        assert len(phases) >= 2
        assert phases[0]["name"] == "Foundation"

    def test_phases_in_order(self):
        modules = [
            {"path": "src/pipelines/gold/build.py", "comment": ""},
            {"path": "src/config/settings.py", "comment": ""},
            {"path": "src/pipelines/bronze/ingest.py", "comment": ""},
        ]
        phases = build_phases(modules)
        names = [p["name"] for p in phases]
        assert names.index("Foundation") < names.index("Bronze Layer")
        assert names.index("Bronze Layer") < names.index("Gold Layer")


class TestGenerateImplSequence:
    def test_has_build_phases_section(self):
        modules = [{"path": "src/config/settings.py", "comment": "Config"}]
        phases = build_phases(modules)
        doc = generate_impl_sequence("Test", "test.md", phases, modules, [])
        assert "## 1. Build Phases" in doc

    def test_has_module_build_order(self):
        modules = [{"path": "src/config/settings.py", "comment": "Config"}]
        phases = build_phases(modules)
        doc = generate_impl_sequence("Test", "test.md", phases, modules, [])
        assert "## 2. Module Build Order" in doc
        assert "settings.py" in doc

    def test_has_milestones(self):
        modules = [{"path": "src/config/settings.py", "comment": ""}]
        phases = build_phases(modules)
        doc = generate_impl_sequence("Test", "test.md", phases, modules, [])
        assert "## 3. Milestones" in doc

    def test_includes_traceability(self):
        modules = [{"path": "src/config/settings.py", "comment": ""}]
        phases = build_phases(modules)
        trace = [
            {
                "requirement": "FR-1",
                "drd ref": "DRD §1",
                "implementation component": "build",
                "lld section": "§5",
            }
        ]
        doc = generate_impl_sequence("Test", "test.md", phases, modules, trace)
        assert "## 4. Traceability" in doc
        assert "FR-1" in doc


class TestCLI:
    def test_missing_file_exits_2(self, tmp_path):
        import subprocess

        result = subprocess.run(
            [
                sys.executable,
                str(GENERATOR_DIR / "generate_impl_sequence.py"),
                str(tmp_path / "nonexistent.md"),
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 2

    def test_no_required_sections_exits_1(self, tmp_path):
        import subprocess

        f = tmp_path / "empty.md"
        f.write_text("# LLD\n\n## 7. Config\n\nContent.")
        result = subprocess.run(
            [
                sys.executable,
                str(GENERATOR_DIR / "generate_impl_sequence.py"),
                str(f),
                "-o",
                str(tmp_path / "impl.md"),
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 1

    def test_valid_lld_exits_0(self, tmp_path):
        import subprocess

        f = tmp_path / "valid.md"
        f.write_text(SAMPLE_LLD)
        result = subprocess.run(
            [
                sys.executable,
                str(GENERATOR_DIR / "generate_impl_sequence.py"),
                str(f),
                "-o",
                str(tmp_path / "impl-sequence.md"),
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert (tmp_path / "impl-sequence.md").exists()
