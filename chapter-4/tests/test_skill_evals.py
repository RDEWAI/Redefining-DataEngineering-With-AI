"""Tests that all skill eval-cases.yaml files are well-formed."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

CHAPTER_4 = Path(__file__).resolve().parent.parent

# All skills that should have eval cases (excludes apply-learnings)
EVAL_SKILLS = [
    ("ba-plugin", "create-drd"),
    ("ba-plugin", "update-drd"),
    ("ba-plugin", "validate-drd"),
    ("architect-plugin", "create-hld"),
    ("architect-plugin", "update-hld"),
    ("architect-plugin", "validate-hld"),
    ("data-modeler-plugin", "create-dms"),
    ("data-modeler-plugin", "update-dms"),
    ("data-modeler-plugin", "validate-dms"),
    ("mapping-analyst-plugin", "create-stm"),
    ("mapping-analyst-plugin", "update-stm"),
    ("mapping-analyst-plugin", "validate-stm"),
    ("dq-engineer-plugin", "create-dqs"),
    ("dq-engineer-plugin", "update-dqs"),
    ("dq-engineer-plugin", "validate-dqs"),
    ("dq-engineer-plugin", "generate-se-rules"),
    ("technical-lead-plugin", "create-lld"),
    ("technical-lead-plugin", "update-lld"),
    ("technical-lead-plugin", "validate-lld"),
    ("technical-lead-plugin", "generate-config-template"),
]

VALID_EXPECTED_TYPES = {
    "validation_pass",
    "validation_fail",
    "section_present",
    "sheet_present",
    "content_contains",
    "no_vague_language",
    "asks_question",
    "no_output_generated",
    "file_created",
    "file_count_gt",
    "file_extension",
    "exit_code",
    "yaml_valid",
}


def _eval_paths() -> list[tuple[str, str, Path]]:
    """Return (plugin, skill, path) for all eval-cases.yaml files."""
    return [
        (
            plugin,
            skill,
            CHAPTER_4 / plugin / "skills" / skill / "evals" / "eval-cases.yaml",
        )
        for plugin, skill in EVAL_SKILLS
    ]


ALL_EVALS = _eval_paths()


class TestEvalFilesExist:
    """All expected eval-cases.yaml files must exist."""

    @pytest.mark.parametrize(
        "plugin,skill,path",
        ALL_EVALS,
        ids=[f"{p}/{s}" for p, s, _ in ALL_EVALS],
    )
    def test_eval_file_exists(self, plugin, skill, path):
        assert path.exists(), f"eval-cases.yaml not found at {path}"


class TestEvalFileStructure:
    """Eval YAML files must have required fields and valid structure."""

    @pytest.mark.parametrize(
        "plugin,skill,path",
        ALL_EVALS,
        ids=[f"{p}/{s}" for p, s, _ in ALL_EVALS],
    )
    def test_yaml_parses(self, plugin, skill, path):
        if not path.exists():
            pytest.skip(f"File not found: {path}")
        content = path.read_text(encoding="utf-8")
        data = yaml.safe_load(content)
        assert isinstance(data, dict), "Eval file must be a YAML mapping"

    @pytest.mark.parametrize(
        "plugin,skill,path",
        ALL_EVALS,
        ids=[f"{p}/{s}" for p, s, _ in ALL_EVALS],
    )
    def test_has_skill_field(self, plugin, skill, path):
        if not path.exists():
            pytest.skip(f"File not found: {path}")
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        assert "skill" in data, "Eval file must have 'skill' field"
        assert data["skill"] == skill, f"Eval skill '{data['skill']}' != expected '{skill}'"

    @pytest.mark.parametrize(
        "plugin,skill,path",
        ALL_EVALS,
        ids=[f"{p}/{s}" for p, s, _ in ALL_EVALS],
    )
    def test_has_version(self, plugin, skill, path):
        if not path.exists():
            pytest.skip(f"File not found: {path}")
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        assert "version" in data, "Eval file must have 'version' field"

    @pytest.mark.parametrize(
        "plugin,skill,path",
        ALL_EVALS,
        ids=[f"{p}/{s}" for p, s, _ in ALL_EVALS],
    )
    def test_has_cases(self, plugin, skill, path):
        if not path.exists():
            pytest.skip(f"File not found: {path}")
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        assert "cases" in data, "Eval file must have 'cases' list"
        assert isinstance(data["cases"], list), "'cases' must be a list"
        assert len(data["cases"]) >= 3, "Must have at least 3 test cases"


class TestEvalCaseFields:
    """Each eval case must have required fields."""

    @pytest.mark.parametrize(
        "plugin,skill,path",
        ALL_EVALS,
        ids=[f"{p}/{s}" for p, s, _ in ALL_EVALS],
    )
    def test_cases_have_required_fields(self, plugin, skill, path):
        if not path.exists():
            pytest.skip(f"File not found: {path}")
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        required = {"id", "name", "expected", "success_criteria"}
        for case in data.get("cases", []):
            missing = required - set(case.keys())
            assert not missing, f"Case {case.get('id', '?')} missing fields: {missing}"

    @pytest.mark.parametrize(
        "plugin,skill,path",
        ALL_EVALS,
        ids=[f"{p}/{s}" for p, s, _ in ALL_EVALS],
    )
    def test_case_ids_unique(self, plugin, skill, path):
        if not path.exists():
            pytest.skip(f"File not found: {path}")
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        ids = [c["id"] for c in data.get("cases", []) if "id" in c]
        assert len(ids) == len(set(ids)), f"Duplicate case IDs found in {skill}"

    @pytest.mark.parametrize(
        "plugin,skill,path",
        ALL_EVALS,
        ids=[f"{p}/{s}" for p, s, _ in ALL_EVALS],
    )
    def test_expected_types_valid(self, plugin, skill, path):
        if not path.exists():
            pytest.skip(f"File not found: {path}")
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        for case in data.get("cases", []):
            for exp in case.get("expected", []):
                assert "type" in exp, f"Case {case['id']}: expected entry missing 'type'"
                assert (
                    exp["type"] in VALID_EXPECTED_TYPES
                ), f"Case {case['id']}: unknown expected type '{exp['type']}'"
