"""Tests for the DAG definition generator script."""

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

from generate_dag_definition import (  # noqa: E402
    extract_mermaid,
    extract_subsection,
    generate_dag_yaml,
    parse_dependencies,
    parse_metadata_table,
    parse_sections,
    parse_task_table,
)

SAMPLE_LLD = """\
# Low-Level Design: Test Pipeline

## 1. Design Overview

Test overview.

## 4. DAG Specification

### 4.1 DAG Metadata

| Property | Value |
|----------|-------|
| DAG ID | `test_daily_v1` |
| Schedule | `0 * * * *` (hourly) |
| Timezone | UTC |
| Catchup | Yes |
| Max active runs | 1 |
| Concurrency | 4 |
| Default timeout | 120 minutes |

### 4.2 Task Inventory

| Task ID | Type | Layer | Dependencies | Timeout | Retries | Retry Delay |
|---------|------|-------|-------------|---------|---------|-------------|
| `ingest_a` | PySpark | Bronze | None | 30 min | 3 | 60s exp |
| `ingest_b` | PySpark | Bronze | None | 30 min | 3 | 60s exp |
| `dq_gate_bronze` | Sensor | Gate | `ingest_a`, `ingest_b` | 15 min | 1 | 30s fixed |
| `transform_a` | PySpark | Silver | `dq_gate_bronze` | 45 min | 2 | 120s exp |

### 4.3 DAG Diagram

```mermaid
graph TD
    A[ingest_a] --> DQ1{dq_gate_bronze}
    B[ingest_b] --> DQ1
    DQ1 --> C[transform_a]
```

### 4.4 Critical Path Analysis

The critical path through the DAG is:

```
ingest_a (~5 min)
  --> dq_gate_bronze (~1 min)
  --> transform_a (~10 min)
```

## 5. Task Implementation Details

Some content here.
"""


class TestParseSections:
    def test_parses_sections(self):
        sections = parse_sections(SAMPLE_LLD)
        assert "4. DAG Specification" in sections
        assert "1. Design Overview" in sections

    def test_section_content(self):
        sections = parse_sections(SAMPLE_LLD)
        assert "Task Inventory" in sections["4. DAG Specification"]


class TestExtractSubsection:
    def test_extracts_metadata(self):
        sections = parse_sections(SAMPLE_LLD)
        content = extract_subsection(sections["4. DAG Specification"], "4.1")
        assert "DAG ID" in content

    def test_extracts_task_table(self):
        sections = parse_sections(SAMPLE_LLD)
        content = extract_subsection(sections["4. DAG Specification"], "4.2")
        assert "ingest_a" in content


class TestParseMetadataTable:
    def test_parses_dag_metadata(self):
        sections = parse_sections(SAMPLE_LLD)
        content = extract_subsection(sections["4. DAG Specification"], "4.1")
        metadata = parse_metadata_table(content)
        assert metadata["DAG ID"] == "test_daily_v1"
        assert "UTC" in metadata["Timezone"]


class TestParseTaskTable:
    def test_parses_all_tasks(self):
        sections = parse_sections(SAMPLE_LLD)
        content = extract_subsection(sections["4. DAG Specification"], "4.2")
        tasks = parse_task_table(content)
        assert len(tasks) == 4

    def test_task_has_required_fields(self):
        sections = parse_sections(SAMPLE_LLD)
        content = extract_subsection(sections["4. DAG Specification"], "4.2")
        tasks = parse_task_table(content)
        first = tasks[0]
        assert "task id" in first
        assert "type" in first
        assert "layer" in first


class TestParseDependencies:
    def test_none_returns_empty(self):
        assert parse_dependencies("None") == []

    def test_single_dep(self):
        assert parse_dependencies("`dq_gate_bronze`") == ["dq_gate_bronze"]

    def test_multiple_deps(self):
        result = parse_dependencies("`ingest_a`, `ingest_b`")
        assert len(result) == 2
        assert "ingest_a" in result

    def test_empty_string(self):
        assert parse_dependencies("") == []


class TestExtractMermaid:
    def test_extracts_mermaid(self):
        sections = parse_sections(SAMPLE_LLD)
        mermaid = extract_mermaid(sections["4. DAG Specification"])
        assert mermaid is not None
        assert "graph TD" in mermaid
        assert "ingest_a" in mermaid

    def test_no_mermaid_returns_none(self):
        assert extract_mermaid("No mermaid here") is None


class TestGenerateDagYaml:
    def test_generates_valid_yaml(self):
        metadata = {
            "DAG ID": "test_v1",
            "Schedule": "0 * * * *",
            "Timezone": "UTC",
            "Catchup": "Yes",
            "Max active runs": "1",
            "Concurrency": "4",
            "Default timeout": "120 minutes",
        }
        tasks = [
            {
                "task id": "`ingest_a`",
                "type": "PySpark",
                "layer": "Bronze",
                "dependencies": "None",
                "timeout": "30 min",
                "retries": "3",
                "retry delay": "60s exp",
            },
        ]
        yaml_content = generate_dag_yaml(metadata, tasks, [], "test.md")
        assert "dag_id: test_v1" in yaml_content
        assert "schedule:" in yaml_content
        assert "task_id: ingest_a" in yaml_content

    def test_includes_critical_path(self):
        metadata = {
            "DAG ID": "test_v1",
            "Schedule": "0 * * * *",
            "Timezone": "UTC",
            "Catchup": "No",
            "Max active runs": "1",
            "Concurrency": "1",
            "Default timeout": "60 minutes",
        }
        tasks = [
            {
                "task id": "`a`",
                "type": "PySpark",
                "layer": "Bronze",
                "dependencies": "None",
                "timeout": "30 min",
                "retries": "1",
                "retry delay": "60s",
            }
        ]
        yaml_content = generate_dag_yaml(metadata, tasks, ["a", "b"], "test.md")
        assert "critical_path:" in yaml_content
        assert "- a" in yaml_content


class TestCLI:
    def test_missing_file_exits_2(self, tmp_path):
        import subprocess

        result = subprocess.run(
            [
                sys.executable,
                str(GENERATOR_DIR / "generate_dag_definition.py"),
                str(tmp_path / "nonexistent.md"),
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 2

    def test_no_section_4_exits_1(self, tmp_path):
        import subprocess

        f = tmp_path / "no-dag.md"
        f.write_text("# LLD\n\n## 1. Design Overview\n\nContent.")
        result = subprocess.run(
            [
                sys.executable,
                str(GENERATOR_DIR / "generate_dag_definition.py"),
                str(f),
                "-o",
                str(tmp_path / "out"),
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
                str(GENERATOR_DIR / "generate_dag_definition.py"),
                str(f),
                "-o",
                str(tmp_path / "dag"),
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert (tmp_path / "dag" / "dag-definition.yaml").exists()
        assert (tmp_path / "dag" / "dag-pipeline.mmd").exists()
