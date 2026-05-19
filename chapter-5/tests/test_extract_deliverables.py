"""Tests for the multi-skill deliverable extraction helper."""

# ruff: noqa: E501

from __future__ import annotations

import sys
from pathlib import Path

STATUS_ROLLUP = (
    Path(__file__).resolve().parents[1]
    / "developer-plugin"
    / "skills"
    / "validate-stories"
    / "scripts"
    / "status_rollup.py"
)
sys.path.insert(0, str(STATUS_ROLLUP.parent))
import status_rollup as sr  # type: ignore[import-not-found]  # noqa: E402


def _write_owners(dirpath: Path) -> None:
    (dirpath / "inputs" / "code" / "v1").mkdir(parents=True, exist_ok=True)
    (dirpath / "inputs" / "code" / "v1" / "DELIVERABLE-OWNERS.yaml").write_text(
        """
version: 1
owners:
  - { glob: "contracts/dq/**",           skill: ingestion }
  - { glob: "contracts/**",              skill: scaffold }
  - { glob: "src/*/bronze/**/*.py",      skill: ingestion }
  - { glob: "src/*/utils/**/*.py",       skill: scaffold }
  - { glob: "airflow/dags/**/*.py",      skill: dag }
  - { glob: "airflow/configs/**/*.yml",  skill: ingestion }
  - { glob: ".github/workflows/**",      skill: pipeline }
  - { glob: "tests/bronze/**",           skill: ingestion }
dispatch_order: [scaffold, ingestion, dag, pipeline]
""",
        encoding="utf-8",
    )


def _ws(root: Path, project_name: str = "demo") -> sr.Workspace:
    return sr.Workspace(
        workspace_root=root,
        project_root=root / project_name,
        project_name=project_name,
        stories_dir=root / "outputs" / "stories",
        learnings_queue=root / "memory" / "developer" / "learnings-queue.jsonl",
    )


def test_glob_to_regex_matches_doublestar(tmp_path: Path) -> None:
    pat = sr._glob_to_regex("contracts/**")
    assert pat.match("contracts/foo.yml")
    assert pat.match("contracts/dq/x.yml")
    assert not pat.match("other/foo.yml")


def test_glob_to_regex_matches_midslash_doublestar(tmp_path: Path) -> None:
    pat = sr._glob_to_regex("airflow/dags/**/*.py")
    assert pat.match("airflow/dags/foo.py")
    assert pat.match("airflow/dags/nested/foo.py")
    assert not pat.match("airflow/configs/foo.py")


def test_longest_glob_wins(tmp_path: Path) -> None:
    _write_owners(tmp_path)
    ws = _ws(tmp_path)
    registry = sr.load_deliverable_owners(ws)
    # Most-specific glob should come first after load-time sort.
    globs = [o["glob"] for o in registry["owners"]]
    assert globs.index("contracts/dq/**") < globs.index("contracts/**")
    skill = sr._skill_for_path("contracts/dq/patients.yml", registry["owners"])
    assert skill == "ingestion"
    skill = sr._skill_for_path("contracts/patients.yml", registry["owners"])
    assert skill == "scaffold"


def test_project_name_prefix_strips(tmp_path: Path) -> None:
    _write_owners(tmp_path)
    ws = _ws(tmp_path, project_name="demo")
    registry = sr.load_deliverable_owners(ws)
    # `demo/src/demo/bronze/runner.py` should still match the
    # `src/*/bronze/**/*.py` glob via the project-prefix strip.
    skill = sr._skill_for_path(
        "demo/src/demo/bronze/runner.py",
        registry["owners"],
        project_name="demo",
    )
    assert skill == "ingestion"


def test_cross_cutting_story_splits_by_skill(tmp_path: Path) -> None:
    _write_owners(tmp_path)
    story_dir = tmp_path / "outputs" / "stories" / "v1" / "EPIC-02-ingestion"
    story_dir.mkdir(parents=True)
    (story_dir / "STORY-02-004-reconciliation.md").write_text(
        """# STORY-02-004 — Reconciliation

| Field | Value |
|-------|-------|
| **Status** | To Do |
| **Epic** | EPIC-02 |
| **Sprint** | Sprint 3 |
| **Dependencies** | None |

## Acceptance Criteria

- [ ] Bronze reconciliation module at `src/demo/bronze/reconciliation_bronze.py` runs query_dq rules [LLD §5.5]
- [ ] `reconciliation_bronze` task wired into `airflow/dags/hourly_v1.py` downstream of `bronze_ingestion` [LLD §4.2]
- [ ] Integration test at `tests/bronze/test_reconciliation.py` asserts task success on local Airflow [LLD §4.3]

## Technical Notes

None.
""",
        encoding="utf-8",
    )
    ws = _ws(tmp_path, project_name="demo")
    result = sr.extract_deliverables(ws, "STORY-02-004")
    assert set(result["by_skill"].keys()) == {"ingestion", "dag"}
    assert "src/demo/bronze/reconciliation_bronze.py" in result["by_skill"]["ingestion"]
    assert "airflow/dags/hourly_v1.py" in result["by_skill"]["dag"]
    assert "tests/bronze/test_reconciliation.py" in result["by_skill"]["ingestion"]
    # dispatch_order respects the registry order: ingestion before dag.
    assert result["dispatch_order"].index("ingestion") < result["dispatch_order"].index("dag")


def test_build_plan_cross_cutting_story(tmp_path: Path) -> None:
    _write_owners(tmp_path)
    story_dir = tmp_path / "outputs" / "stories" / "v1" / "EPIC-02-ingestion"
    story_dir.mkdir(parents=True)
    (story_dir / "STORY-02-004-reconciliation.md").write_text(
        """# STORY-02-004

| Field | Value |
|-------|-------|
| **Status** | To Do |
| **Epic** | EPIC-02 |
| **Sprint** | Sprint 3 |
| **Dependencies** | None |

## Acceptance Criteria

- [ ] `src/demo/bronze/reconciliation_bronze.py` runs query_dq rules
- [ ] `airflow/dags/hourly_v1.py` wires the reconciliation task downstream

## Technical Notes
""",
        encoding="utf-8",
    )
    ws = _ws(tmp_path, project_name="demo")
    plan = sr.build_plan(ws, "STORY-02-004")
    # Two tasks, depend_on chain ingestion→dag (per dispatch_order).
    assert len(plan["tasks"]) == 2
    assert plan["tasks"][0]["kind"] == "ingestion"
    assert plan["tasks"][1]["kind"] == "dag"
    assert plan["tasks"][1]["depends_on"] == ["T1"]
    # ACs map to their owning tasks.
    assert plan["acceptance_criteria"][0]["task_ids"] == ["T1"]
    assert plan["acceptance_criteria"][1]["task_ids"] == ["T2"]
    assert plan["status"] == "planned"


def test_plan_save_load_roundtrip(tmp_path: Path) -> None:
    _write_owners(tmp_path)
    story_dir = tmp_path / "outputs" / "stories" / "v1" / "EPIC-01-foundation"
    story_dir.mkdir(parents=True)
    (story_dir / "STORY-01-001-scaffold.md").write_text(
        """# STORY-01-001

| Field | Value |
|-------|-------|
| **Status** | To Do |
| **Epic** | EPIC-01 |
| **Sprint** | Sprint 1 |
| **Dependencies** | None |

## Acceptance Criteria

- [ ] `pyproject.toml` is valid

## Technical Notes
""",
        encoding="utf-8",
    )
    ws = _ws(tmp_path, project_name="demo")
    plan = sr.build_plan(ws, "STORY-01-001")
    path = sr.save_plan(ws, plan)
    assert path.is_file()
    loaded = sr.load_plan(ws, "STORY-01-001")
    assert loaded is not None
    assert loaded["story_id"] == "STORY-01-001"
    assert loaded["generated_at"] is not None
    # Re-save bumps plan_version.
    plan2 = sr.build_plan(ws, "STORY-01-001")
    sr.save_plan(ws, plan2)
    loaded2 = sr.load_plan(ws, "STORY-01-001")
    assert loaded2["plan_version"] == 2


def test_wildcard_token_expands_against_workspace(tmp_path: Path) -> None:
    """A `prefix_*.yml` token in an AC expands to matching files on disk."""
    _write_owners(tmp_path)
    # Workspace-relative contract files (matching the cookiecutter layout).
    contracts_dir = tmp_path / "demo" / "contracts"
    contracts_dir.mkdir(parents=True)
    for name in ("synthea_patients.yml", "synthea_encounters.yml", "synthea_claims.yml"):
        (contracts_dir / name).write_text("columns: []\n", encoding="utf-8")
    (contracts_dir / "clinical_patients.yml").write_text("columns: []\n", encoding="utf-8")
    story_dir = tmp_path / "outputs" / "stories" / "v1" / "EPIC-01-foundation"
    story_dir.mkdir(parents=True)
    (story_dir / "STORY-01-003-schema-contracts.md").write_text(
        """# STORY-01-003

| Field | Value |
|-------|-------|
| **Status** | To Do |
| **Epic** | EPIC-01 |
| **Sprint** | Sprint 1 |
| **Dependencies** | None |

## Acceptance Criteria

- [ ] Bronze contracts under `demo/contracts/synthea_*.yml`
- [ ] Silver contracts under `demo/contracts/clinical_*.yml`

## Technical Notes
""",
        encoding="utf-8",
    )
    ws = _ws(tmp_path, project_name="demo")
    result = sr.extract_deliverables(ws, "STORY-01-003")
    # Wildcard expanded to 3 synthea files + 1 clinical file = 4 paths total.
    assert len(result["paths"]) == 4
    assert "demo/contracts/synthea_patients.yml" in result["paths"]
    assert "demo/contracts/clinical_patients.yml" in result["paths"]
    # All routed to scaffold (contracts/** glob).
    assert set(result["by_skill"].keys()) == {"scaffold"}
    assert len(result["by_skill"]["scaffold"]) == 4


def test_wildcard_token_with_no_matches_keeps_token(tmp_path: Path) -> None:
    """A wildcard token that matches no files on disk falls through unchanged."""
    _write_owners(tmp_path)
    story_dir = tmp_path / "outputs" / "stories" / "v1" / "EPIC-01-foundation"
    story_dir.mkdir(parents=True)
    (story_dir / "STORY-01-099-future.md").write_text(
        """# STORY-01-099

| Field | Value |
|-------|-------|
| **Status** | To Do |
| **Epic** | EPIC-01 |
| **Sprint** | Sprint 1 |
| **Dependencies** | None |

## Acceptance Criteria

- [ ] Future contracts under `demo/contracts/future_*.yml`

## Technical Notes
""",
        encoding="utf-8",
    )
    ws = _ws(tmp_path, project_name="demo")
    result = sr.extract_deliverables(ws, "STORY-01-099")
    # No matches on disk → original token kept (with `*` collapsed via _strip_placeholder_segments).
    assert result["paths"] == ["demo/contracts/future_*.yml"]


def test_behavioural_story_with_no_paths_falls_back_to_classifier(
    tmp_path: Path,
) -> None:
    _write_owners(tmp_path)
    story_dir = tmp_path / "outputs" / "stories" / "v1" / "EPIC-02-bronze-ingestion"
    story_dir.mkdir(parents=True)
    (story_dir / "STORY-02-010-ingestion-runner.md").write_text(
        """# STORY-02-010

| Field | Value |
|-------|-------|
| **Status** | To Do |
| **Epic** | EPIC-02 |
| **Sprint** | Sprint 3 |
| **Dependencies** | None |

## Acceptance Criteria

- [ ] The ingestion runner accepts a config path and an env
- [ ] Reads DuckDB read-only; no writes to source

## Technical Notes
""",
        encoding="utf-8",
    )
    ws = _ws(tmp_path, project_name="demo")
    result = sr.extract_deliverables(ws, "STORY-02-010")
    assert result["paths"] == []
    assert result["by_skill"] == {}
    # Classifier kicks in — story slug `ingestion-runner` → ingestion.
    assert result["fallback_kind"] == "ingestion"
