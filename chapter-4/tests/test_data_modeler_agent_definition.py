"""Tests for the data modeler agent definition file structure and content."""

from __future__ import annotations

from pathlib import Path

import yaml

AGENT_FILE = (
    Path(__file__).resolve().parent.parent
    / "data-modeler-plugin"
    / "agents"
    / "data-modeler-agent.md"
)


def _parse_agent_file() -> tuple[dict, str]:
    """Parse the agent markdown file into frontmatter and body."""
    content = AGENT_FILE.read_text(encoding="utf-8")
    assert content.startswith("---"), "Must start with YAML frontmatter"

    parts = content.split("---", 2)
    assert len(parts) >= 3, "Must have --- delimited frontmatter"

    frontmatter = yaml.safe_load(parts[1])
    body = parts[2]
    return frontmatter, body


class TestAgentFileExists:
    """The agent file must exist at the expected location."""

    def test_file_exists(self):
        assert AGENT_FILE.exists(), f"Not found at {AGENT_FILE}"

    def test_file_is_markdown(self):
        assert AGENT_FILE.suffix == ".md"


class TestAgentFrontmatter:
    """YAML frontmatter must contain required fields."""

    def test_name_is_data_modeler_agent(self):
        fm, _ = _parse_agent_file()
        assert fm["name"] == "data-modeler-agent"

    def test_model_is_inherit(self):
        fm, _ = _parse_agent_file()
        assert fm["model"] == "inherit"

    def test_has_description(self):
        fm, _ = _parse_agent_file()
        assert "description" in fm
        assert len(fm["description"]) > 50

    def test_tools_include_required_set(self):
        fm, _ = _parse_agent_file()
        tools = set(fm["tools"])
        required = {"Read", "Write", "Edit", "Bash", "Grep", "Glob"}
        assert required.issubset(tools), f"Missing: {required - tools}"

    def test_tools_include_ask_user_question(self):
        fm, _ = _parse_agent_file()
        ask = [t for t in fm["tools"] if "AskUserQuestion" in t]
        assert len(ask) >= 1, "Must have AskUserQuestion tool"

    def test_has_color(self):
        fm, _ = _parse_agent_file()
        assert "color" in fm

    def test_description_contains_examples(self):
        fm, _ = _parse_agent_file()
        assert "<example>" in fm["description"]


class TestAgentSystemPrompt:
    """The system prompt body must contain key sections."""

    def test_has_schema_design_focus(self):
        _, body = _parse_agent_file()
        assert "bronze" in body.lower()
        assert "silver" in body.lower()
        assert "gold" in body.lower()

    def test_has_four_responsibilities(self):
        _, body = _parse_agent_file()
        assert "Bronze Layer Schema" in body
        assert "Silver Layer Schema" in body
        assert "Gold Layer Schema" in body
        assert "Naming Convention" in body

    def test_has_hld_traceability_enforcement(self):
        _, body = _parse_agent_file()
        assert "HLD" in body
        assert "traceab" in body.lower() or "cite" in body.lower()

    def test_has_workflow_phases(self):
        _, body = _parse_agent_file()
        for phase in ["Phase 1", "Phase 2", "Phase 3", "Phase 4", "Phase 5"]:
            assert phase in body, f"Missing {phase}"

    def test_has_pitfall_prevention(self):
        _, body = _parse_agent_file()
        assert "Pitfall" in body or "pitfall" in body
        assert "DESCRIBE" in body or "source" in body.lower()

    def test_has_anti_patterns(self):
        _, body = _parse_agent_file()
        assert "Anti-Pattern" in body or "Anti-pattern" in body

    def test_references_skill_paths(self):
        _, body = _parse_agent_file()
        assert "create-dms" in body
        assert "update-dms" in body
        assert "validate-dms" in body

    def test_enforces_readonly_database(self):
        _, body = _parse_agent_file()
        assert "-readonly" in body

    def test_blocks_on_missing_database(self):
        _, body = _parse_agent_file()
        assert "STOP" in body or "Do NOT proceed" in body

    def test_references_memory_directory(self):
        _, body = _parse_agent_file()
        assert "data-modeler-plugin/memory/" in body

    def test_instructs_ask_user_question(self):
        _, body = _parse_agent_file()
        assert "AskUserQuestion" in body

    def test_has_decision_documentation_format(self):
        _, body = _parse_agent_file()
        assert "Options Considered" in body or "Rationale" in body
        assert "Trade-off" in body or "trade-off" in body

    def test_references_dms_sections(self):
        _, body = _parse_agent_file()
        assert "Design Overview" in body
        assert "Bronze Layer Schema" in body
        assert "Silver Layer Schema" in body
        assert "Gold Layer Schema" in body
        assert "SCD Strategy" in body
        assert "Naming Convention" in body
        assert "Traceability Matrix" in body

    def test_has_scd_type_framework(self):
        _, body = _parse_agent_file()
        assert "SCD" in body or "scd" in body
        assert "Type 1" in body or "Type 2" in body

    def test_has_yaml_schema_block_guidance(self):
        _, body = _parse_agent_file()
        assert "YAML" in body or "yaml" in body

    def test_has_versioned_discovery(self):
        _, body = _parse_agent_file()
        assert "sort -V" in body, "Agent must use version-sorted discovery for inputs"

    def test_agent_has_subagent_fallback(self):
        """Agent must have fallback format for when AskUserQuestion is unavailable."""
        _, body = _parse_agent_file()
        assert "subagent" in body.lower() or "fallback" in body.lower()
        # Check for lettered options pattern
        assert "A)" in body or "A) " in body
