"""Tests that all chapter-5-local skill eval-cases.yaml files are well-formed.

Planning-plugin evals are tested by chapter-4's test suite.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

CHAPTER_5 = Path(__file__).resolve().parent.parent

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
    """Return (plugin, skill, path) for every eval-cases.yaml under chapter-5 plugins."""
    results: list[tuple[str, str, Path]] = []
    for plugin in ("scrum-master-plugin", "developer-plugin"):
        skills_root = CHAPTER_5 / plugin / "skills"
        if not skills_root.exists():
            continue
        for eval_file in skills_root.rglob("evals/eval-cases.yaml"):
            skill_name = eval_file.parent.parent.relative_to(skills_root).as_posix()
            results.append((plugin, skill_name, eval_file))
    return results


EVAL_FILES = _eval_paths()


@pytest.mark.parametrize(
    "plugin,skill,path",
    EVAL_FILES,
    ids=[f"{p}/{s}" for p, s, _ in EVAL_FILES],
)
def test_eval_yaml_valid(plugin, skill, path):
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(data, (dict, list)), f"{path} must parse as YAML mapping or list"
