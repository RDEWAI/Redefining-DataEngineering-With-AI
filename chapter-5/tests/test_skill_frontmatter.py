"""Tests that all SKILL.md files in chapter-5 plugins have required Skills 2.0 frontmatter fields.

The planning plugins (ba/architect/data-modeler/mapping-analyst/dq-engineer/
technical-lead) are sourced from chapter-4 and are tested by chapter-4's own
test suite. This file only covers chapter-5-local plugins.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

CHAPTER_5 = Path(__file__).resolve().parent.parent


def _all_skill_paths() -> list[tuple[str, str, Path]]:
    """Return (plugin, skill, path) tuples for every SKILL.md under chapter-5 plugins."""
    results: list[tuple[str, str, Path]] = []
    for plugin in ("scrum-master-plugin", "developer-plugin"):
        skills_root = CHAPTER_5 / plugin / "skills"
        if not skills_root.exists():
            continue
        for skill_md in skills_root.rglob("SKILL.md"):
            skill_name = skill_md.parent.relative_to(skills_root).as_posix()
            results.append((plugin, skill_name, skill_md))
    return results


def _parse_skill(path: Path) -> tuple[dict, str]:
    """Parse SKILL.md into frontmatter dict and body string."""
    content = path.read_text(encoding="utf-8")
    assert content.startswith("---"), f"{path} must start with YAML frontmatter"
    parts = content.split("---", 2)
    assert len(parts) >= 3, f"{path} must have --- delimited frontmatter"
    frontmatter = yaml.safe_load(parts[1])
    body = parts[2]
    return frontmatter, body


ALL_SKILLS = _all_skill_paths()
CORE_SKILLS = [(p, s, path) for p, s, path in ALL_SKILLS if Path(s).name != "apply-learnings"]


class TestSkillFrontmatter:
    """YAML frontmatter must contain required Skills 2.0 fields."""

    @pytest.mark.parametrize(
        "plugin,skill,path",
        CORE_SKILLS,
        ids=[f"{p}/{s}" for p, s, _ in CORE_SKILLS],
    )
    def test_has_name(self, plugin, skill, path):
        fm, _ = _parse_skill(path)
        assert "name" in fm, f"{skill} missing 'name' field"

    @pytest.mark.parametrize(
        "plugin,skill,path",
        CORE_SKILLS,
        ids=[f"{p}/{s}" for p, s, _ in CORE_SKILLS],
    )
    def test_has_description(self, plugin, skill, path):
        fm, _ = _parse_skill(path)
        assert "description" in fm, f"{skill} missing 'description'"


def test_chapter5_has_local_plugins():
    """Sanity check: chapter-5 still ships scrum-master and developer plugins."""
    assert (CHAPTER_5 / "scrum-master-plugin" / "skills").exists()
    assert (CHAPTER_5 / "developer-plugin" / "skills").exists()
