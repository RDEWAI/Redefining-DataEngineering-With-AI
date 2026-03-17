"""Tests for the mapping analyst agent definition file structure and content."""

from __future__ import annotations

from pathlib import Path

import yaml

AGENT_FILE = (
    Path(__file__).resolve().parent.parent
    / "mapping-analyst-plugin"
    / "agents"
    / "mapping-analyst-agent.md"
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

    def test_name_is_mapping_analyst_agent(self):
        fm, _ = _parse_agent_file()
        assert fm["name"] == "mapping-analyst-agent"

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

    def test_has_mapping_focus(self):
        _, body = _parse_agent_file()
        assert "source-to-bronze" in body.lower() or "Source-to-Bronze" in body
        assert "bronze-to-silver" in body.lower() or "Bronze-to-Silver" in body
        assert "silver-to-gold" in body.lower() or "Silver-to-Gold" in body

    def test_has_four_responsibilities(self):
        _, body = _parse_agent_file()
        assert "Source-to-Bronze" in body
        assert "Bronze-to-Silver" in body
        assert "Silver-to-Gold" in body
        assert "Lineage" in body or "lineage" in body

    def test_has_dms_traceability_enforcement(self):
        _, body = _parse_agent_file()
        assert "DMS" in body
        assert "traceab" in body.lower() or "cite" in body.lower()

    def test_has_workflow_phases(self):
        _, body = _parse_agent_file()
        for phase in ["Phase 1", "Phase 2", "Phase 3", "Phase 4", "Phase 5"]:
            assert phase in body, f"Missing {phase}"

    def test_has_pitfall_prevention(self):
        _, body = _parse_agent_file()
        assert "Pitfall" in body or "pitfall" in body
        assert "DESCRIBE" in body or "metadata" in body.lower()

    def test_has_anti_patterns(self):
        _, body = _parse_agent_file()
        assert "Anti-Pattern" in body or "Anti-pattern" in body or "pitfall" in body.lower()

    def test_references_skill_paths(self):
        _, body = _parse_agent_file()
        assert "skills/create-stm/SKILL.md" in body
        assert "skills/update-stm/SKILL.md" in body
        assert "skills/validate-stm/SKILL.md" in body

    def test_enforces_readonly_database(self):
        _, body = _parse_agent_file()
        assert "-readonly" in body or "read-only" in body.lower() or "SELECT" in body

    def test_blocks_on_missing_database(self):
        _, body = _parse_agent_file()
        assert "STOP" in body or "Do NOT proceed" in body or "MUST" in body

    def test_references_memory_directory(self):
        _, body = _parse_agent_file()
        assert "mapping-analyst-plugin/memory/" in body

    def test_instructs_ask_user_question(self):
        _, body = _parse_agent_file()
        assert "AskUserQuestion" in body

    def test_has_decision_documentation_format(self):
        _, body = _parse_agent_file()
        assert "DMS" in body
        assert "Trade-off" in body or "trade-off" in body or "Rationale" in body

    def test_references_stm_sheets(self):
        _, body = _parse_agent_file()
        assert "Summary" in body
        assert "Source-to-Bronze" in body
        assert "Bronze-to-Silver" in body
        assert "Silver-to-Gold" in body
        assert "Code Systems" in body
        assert "Null Handling" in body
        assert "Edge Cases" in body
        assert "Lineage" in body

    def test_has_xlsx_output_references(self):
        _, body = _parse_agent_file()
        assert "xlsx" in body.lower() or "openpyxl" in body.lower()

    def test_has_openpyxl_references(self):
        _, body = _parse_agent_file()
        assert "openpyxl" in body

    def test_has_versioned_discovery(self):
        _, body = _parse_agent_file()
        assert "sort -V" in body, "Agent must use version-sorted discovery for inputs"
