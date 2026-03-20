"""Tests for the architect agent definition file structure and content."""

from __future__ import annotations

from pathlib import Path

import yaml

AGENT_FILE = (
    Path(__file__).resolve().parent.parent / "architect-plugin" / "agents" / "architect-agent.md"
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

    def test_name_is_architect_agent(self):
        fm, _ = _parse_agent_file()
        assert fm["name"] == "architect-agent"

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

    def test_has_architecture_pattern_framework(self):
        _, body = _parse_agent_file()
        assert "Medallion" in body
        assert "Lambda" in body or "Kappa" in body
        assert "Data Vault" in body

    def test_has_four_responsibilities(self):
        _, body = _parse_agent_file()
        assert "Architecture Pattern" in body or "Pattern Selection" in body
        assert "Technology Selection" in body or "Technology" in body
        assert "Layer Design" in body or "Layer Specifications" in body
        assert "Non-Functional" in body or "Capacity" in body

    def test_has_traceability_enforcement(self):
        _, body = _parse_agent_file()
        assert "DRD" in body
        assert "traceab" in body.lower() or "cite" in body.lower()

    def test_has_workflow_phases(self):
        _, body = _parse_agent_file()
        for phase in ["Phase 1", "Phase 2", "Phase 3", "Phase 4", "Phase 5"]:
            assert phase in body, f"Missing {phase}"

    def test_has_pitfall_prevention(self):
        _, body = _parse_agent_file()
        assert "Pitfall" in body or "pitfall" in body
        assert "resume" in body.lower() or "over-engineer" in body.lower()

    def test_has_anti_patterns(self):
        _, body = _parse_agent_file()
        assert "Anti-Pattern" in body or "Anti-pattern" in body

    def test_references_skill_paths(self):
        _, body = _parse_agent_file()
        assert "create-hld" in body
        assert "update-hld" in body
        assert "validate-hld" in body

    def test_enforces_readonly_database(self):
        _, body = _parse_agent_file()
        assert "-readonly" in body

    def test_blocks_on_missing_database(self):
        _, body = _parse_agent_file()
        assert "STOP" in body or "Do NOT proceed" in body

    def test_references_memory_directory(self):
        _, body = _parse_agent_file()
        assert "architect-plugin/memory/" in body

    def test_instructs_ask_user_question(self):
        _, body = _parse_agent_file()
        assert "AskUserQuestion" in body

    def test_has_decision_documentation_format(self):
        _, body = _parse_agent_file()
        assert "Options Considered" in body or "Rationale" in body
        assert "Trade-off" in body or "trade-off" in body

    def test_references_hld_sections(self):
        _, body = _parse_agent_file()
        assert "Executive Summary" in body
        assert "Architecture Overview" in body
        assert "Data Architecture" in body or "Layer Design" in body
        assert "Technology Decisions" in body
        assert "CDC" in body
        assert "Scalability" in body or "Capacity" in body

    def test_references_architect_inputs(self):
        _, body = _parse_agent_file()
        assert "infrastructure-constraints" in body or "Infrastructure" in body
        assert "team-capabilities" in body or "Team Capabilities" in body
        assert "technology-catalog" in body or "Technology Catalog" in body

    def test_has_versioned_discovery(self):
        _, body = _parse_agent_file()
        assert "sort -V" in body, "Agent must use version-sorted discovery for inputs"

    def test_agent_has_subagent_fallback(self):
        """Agent must have fallback format for when AskUserQuestion is unavailable."""
        _, body = _parse_agent_file()
        assert "subagent" in body.lower() or "fallback" in body.lower()
        # Check for lettered options pattern
        assert "A)" in body or "A) " in body
