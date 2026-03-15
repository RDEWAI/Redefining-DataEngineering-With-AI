"""Tests for the BA agent definition file structure and content."""

from __future__ import annotations

from pathlib import Path

import yaml

AGENT_FILE = Path(__file__).resolve().parent.parent / "ba-plugin" / "agents" / "ba-agent.md"


def _parse_agent_file() -> tuple[dict, str]:
    """Parse the agent markdown file into frontmatter dict and body string."""
    content = AGENT_FILE.read_text(encoding="utf-8")
    assert content.startswith("---"), "Agent file must start with YAML frontmatter"

    # Split on the second '---' to separate frontmatter from body
    parts = content.split("---", 2)
    assert len(parts) >= 3, "Agent file must have --- delimited frontmatter"

    frontmatter = yaml.safe_load(parts[1])
    body = parts[2]
    return frontmatter, body


class TestAgentFileExists:
    """The agent file must exist at the expected location."""

    def test_file_exists(self):
        assert AGENT_FILE.exists(), f"Agent file not found at {AGENT_FILE}"

    def test_file_is_markdown(self):
        assert AGENT_FILE.suffix == ".md"


class TestAgentFrontmatter:
    """YAML frontmatter must contain required fields with correct values."""

    def test_name_is_ba_agent(self):
        fm, _ = _parse_agent_file()
        assert fm["name"] == "ba-agent"

    def test_model_is_inherit(self):
        fm, _ = _parse_agent_file()
        assert fm["model"] == "inherit"

    def test_has_description(self):
        fm, _ = _parse_agent_file()
        assert "description" in fm
        assert len(fm["description"]) > 50, "Description should be detailed"

    def test_tools_include_required_set(self):
        fm, _ = _parse_agent_file()
        tools = fm["tools"]
        required_tools = {"Read", "Write", "Edit", "Bash", "Grep", "Glob"}
        assert required_tools.issubset(set(tools)), f"Missing tools: {required_tools - set(tools)}"

    def test_tools_include_ask_user_question(self):
        fm, _ = _parse_agent_file()
        tools = fm["tools"]
        ask_tools = [t for t in tools if "AskUserQuestion" in t]
        assert len(ask_tools) >= 1, "Agent must have AskUserQuestion tool for interactive Q&A"

    def test_has_color(self):
        fm, _ = _parse_agent_file()
        assert "color" in fm

    def test_description_contains_examples(self):
        fm, _ = _parse_agent_file()
        desc = fm["description"]
        assert "<example>" in desc, "Description should contain <example> blocks"


class TestAgentSystemPrompt:
    """The system prompt body must contain key sections."""

    def test_has_elicitation_protocol(self):
        _, body = _parse_agent_file()
        assert "Requirements Elicitation Protocol" in body

    def test_has_responsibilities(self):
        _, body = _parse_agent_file()
        assert "Source Discovery" in body
        assert "Business Rules" in body
        assert "Consumer Requirements" in body
        assert "Quality Expectations" in body

    def test_has_workflow_phases(self):
        _, body = _parse_agent_file()
        assert "Phase 1:" in body or "Phase 1" in body
        assert "Phase 2:" in body or "Phase 2" in body
        assert "Phase 3:" in body or "Phase 3" in body
        assert "Phase 4:" in body or "Phase 4" in body
        assert "Phase 5:" in body or "Phase 5" in body

    def test_has_pitfall_prevention(self):
        _, body = _parse_agent_file()
        assert "Pitfall Prevention" in body
        assert "Accepting Vague Requirements" in body
        assert "Skipping Source Exploration" in body
        assert "Gold-Plating" in body

    def test_has_anti_patterns_table(self):
        _, body = _parse_agent_file()
        assert "Anti-Patterns" in body or "Anti-patterns" in body
        assert "Vague Answer" in body

    def test_references_skill_paths(self):
        _, body = _parse_agent_file()
        assert "skills/create-drd/SKILL.md" in body
        assert "skills/update-drd/SKILL.md" in body
        assert "skills/validate-drd/SKILL.md" in body

    def test_has_versioned_discovery(self):
        _, body = _parse_agent_file()
        assert "sort -V" in body, "Agent must use version-sorted discovery for inputs"

    def test_enforces_readonly_database(self):
        _, body = _parse_agent_file()
        assert "-readonly" in body
        assert "read-only SELECT" in body or "read-only" in body

    def test_blocks_on_missing_database(self):
        _, body = _parse_agent_file()
        assert (
            "STOP" in body and "Do NOT proceed" in body
        ), "Agent must hard-stop when database is inaccessible, not proceed with estimates"
        assert "Do NOT generate a DRD with unverified data" in body
        assert "Do NOT fall back to document estimates" in body

    def test_references_memory_directory(self):
        _, body = _parse_agent_file()
        assert "ba-plugin/memory/" in body

    def test_instructs_ask_user_question_tool_usage(self):
        _, body = _parse_agent_file()
        assert (
            "AskUserQuestion" in body
        ), "System prompt must instruct agent to use AskUserQuestion tool"
        assert "NEVER print questions as text" in body

    def test_has_section_readiness_checklist(self):
        _, body = _parse_agent_file()
        assert "Executive Summary" in body
        assert "Business Context" in body
        assert "Source Discovery" in body
        assert "Data Quality" in body
        assert "Consumer Requirements" in body
        assert "Business Rules" in body
        assert "Regulatory" in body
