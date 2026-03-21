"""Tests that all SKILL.md files have required Skills 2.0 frontmatter fields."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

CHAPTER_4 = Path(__file__).resolve().parent.parent

# All plugins and their skills
PLUGINS = {
    "ba-plugin": ["create-drd", "update-drd", "validate-drd", "apply-learnings"],
    "architect-plugin": [
        "create-hld",
        "update-hld",
        "validate-hld",
        "apply-learnings",
    ],
    "data-modeler-plugin": [
        "create-dms",
        "update-dms",
        "validate-dms",
        "apply-learnings",
    ],
    "mapping-analyst-plugin": [
        "create-stm",
        "update-stm",
        "validate-stm",
        "apply-learnings",
    ],
    "dq-engineer-plugin": [
        "create-dqs",
        "update-dqs",
        "validate-dqs",
        "generate-se-rules",
        "apply-learnings",
    ],
}

# Skills that should have context: fork
FORK_SKILLS = {
    "create-drd",
    "create-hld",
    "create-dms",
    "create-stm",
    "create-dqs",
    "update-drd",
    "update-hld",
    "update-dms",
    "update-stm",
    "update-dqs",
    "generate-se-rules",
}


def _all_skill_paths() -> list[tuple[str, str, Path]]:
    """Return (plugin, skill, path) tuples for all SKILL.md files."""
    results = []
    for plugin, skills in PLUGINS.items():
        for skill in skills:
            path = CHAPTER_4 / plugin / "skills" / skill / "SKILL.md"
            results.append((plugin, skill, path))
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


class TestSkillFilesExist:
    """All expected SKILL.md files must exist."""

    @pytest.mark.parametrize(
        "plugin,skill,path",
        ALL_SKILLS,
        ids=[f"{p}/{s}" for p, s, _ in ALL_SKILLS],
    )
    def test_skill_file_exists(self, plugin, skill, path):
        assert path.exists(), f"SKILL.md not found at {path}"


# Filter to only core skills (not apply-learnings) for frontmatter checks
CORE_SKILLS = [(p, s, path) for p, s, path in ALL_SKILLS if s != "apply-learnings"]


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
        assert fm["name"] == skill

    @pytest.mark.parametrize(
        "plugin,skill,path",
        CORE_SKILLS,
        ids=[f"{p}/{s}" for p, s, _ in CORE_SKILLS],
    )
    def test_has_enhanced_description(self, plugin, skill, path):
        fm, _ = _parse_skill(path)
        assert "description" in fm, f"{skill} missing 'description'"
        desc = fm["description"].lower()
        assert "use when" in desc, f"{skill} description must include 'Use when' trigger phrases"

    @pytest.mark.parametrize(
        "plugin,skill,path",
        CORE_SKILLS,
        ids=[f"{p}/{s}" for p, s, _ in CORE_SKILLS],
    )
    def test_has_allowed_tools(self, plugin, skill, path):
        fm, _ = _parse_skill(path)
        assert "allowed-tools" in fm, f"{skill} missing 'allowed-tools'"

    @pytest.mark.parametrize(
        "plugin,skill,path",
        CORE_SKILLS,
        ids=[f"{p}/{s}" for p, s, _ in CORE_SKILLS],
    )
    def test_has_hooks(self, plugin, skill, path):
        fm, _ = _parse_skill(path)
        assert "hooks" in fm, f"{skill} missing 'hooks' in frontmatter"
        hooks = fm["hooks"]
        assert "before" in hooks, f"{skill} missing 'before' hook"

    @pytest.mark.parametrize(
        "plugin,skill,path",
        [(p, s, path) for p, s, path in CORE_SKILLS if s in FORK_SKILLS],
        ids=[f"{p}/{s}" for p, s, _ in CORE_SKILLS if s in FORK_SKILLS],
    )
    def test_fork_skills_have_context(self, plugin, skill, path):
        fm, _ = _parse_skill(path)
        assert fm.get("context") == "fork", f"{skill} should have 'context: fork' in frontmatter"

    @pytest.mark.parametrize(
        "plugin,skill,path",
        [(p, s, path) for p, s, path in CORE_SKILLS if s not in FORK_SKILLS],
        ids=[f"{p}/{s}" for p, s, _ in CORE_SKILLS if s not in FORK_SKILLS],
    )
    def test_inline_skills_no_fork(self, plugin, skill, path):
        fm, _ = _parse_skill(path)
        assert (
            fm.get("context") != "fork"
        ), f"{skill} should NOT have 'context: fork' (stays inline)"


class TestSkillLearningsSection:
    """All core skills must have a Learnings & Corrections section."""

    @pytest.mark.parametrize(
        "plugin,skill,path",
        CORE_SKILLS,
        ids=[f"{p}/{s}" for p, s, _ in CORE_SKILLS],
    )
    def test_has_learnings_section(self, plugin, skill, path):
        _, body = _parse_skill(path)
        assert (
            "## Learnings & Corrections" in body
        ), f"{skill} missing '## Learnings & Corrections' section"

    @pytest.mark.parametrize(
        "plugin,skill,path",
        CORE_SKILLS,
        ids=[f"{p}/{s}" for p, s, _ in CORE_SKILLS],
    )
    def test_has_meta_rules(self, plugin, skill, path):
        _, body = _parse_skill(path)
        assert (
            "Meta-rules for adding learnings" in body
        ), f"{skill} missing meta-rules in learnings section"

    @pytest.mark.parametrize(
        "plugin,skill,path",
        CORE_SKILLS,
        ids=[f"{p}/{s}" for p, s, _ in CORE_SKILLS],
    )
    def test_has_active_learnings_subsection(self, plugin, skill, path):
        _, body = _parse_skill(path)
        assert "### Active Learnings" in body, f"{skill} missing '### Active Learnings' subsection"


class TestLearningsQueueFiles:
    """Each plugin must have a learnings-queue.jsonl file."""

    @pytest.mark.parametrize("plugin", PLUGINS.keys())
    def test_learnings_queue_exists(self, plugin):
        path = CHAPTER_4 / plugin / "memory" / "learnings-queue.jsonl"
        assert path.exists(), f"learnings-queue.jsonl not found at {path}"


class TestApplyLearningsSkill:
    """Each plugin must have an apply-learnings skill."""

    @pytest.mark.parametrize("plugin", PLUGINS.keys())
    def test_apply_learnings_exists(self, plugin):
        path = CHAPTER_4 / plugin / "skills" / "apply-learnings" / "SKILL.md"
        assert path.exists(), f"apply-learnings SKILL.md not found at {path}"

    @pytest.mark.parametrize("plugin", PLUGINS.keys())
    def test_apply_learnings_has_frontmatter(self, plugin):
        path = CHAPTER_4 / plugin / "skills" / "apply-learnings" / "SKILL.md"
        fm, _ = _parse_skill(path)
        assert fm["name"] == "apply-learnings"
