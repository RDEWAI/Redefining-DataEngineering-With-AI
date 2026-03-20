"""Tests for the DQ engineer agent definition file structure and content."""

from __future__ import annotations

from pathlib import Path

import yaml

AGENT_FILE = (
    Path(__file__).resolve().parent.parent
    / "dq-engineer-plugin"
    / "agents"
    / "dq-engineer-agent.md"
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

    def test_name_is_dq_engineer_agent(self):
        fm, _ = _parse_agent_file()
        assert fm["name"] == "dq-engineer-agent"

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

    def test_has_color_red(self):
        fm, _ = _parse_agent_file()
        assert fm.get("color") == "red"

    def test_description_contains_examples(self):
        fm, _ = _parse_agent_file()
        assert "<example>" in fm["description"]


class TestAgentSystemPrompt:
    """The system prompt body must contain key sections."""

    def test_has_dq_focus(self):
        _, body = _parse_agent_file()
        assert "Field-Level" in body
        assert "Reconciliation" in body

    def test_has_four_responsibilities(self):
        _, body = _parse_agent_file()
        assert "Field-Level Validation" in body
        assert "Referential Integrity" in body
        assert "Statistical Distribution" in body
        assert "Reconciliation" in body

    def test_has_upstream_traceability(self):
        _, body = _parse_agent_file()
        assert "STM" in body
        assert "DMS" in body
        assert "DRD" in body

    def test_has_workflow_phases(self):
        _, body = _parse_agent_file()
        for phase in ["Phase 1", "Phase 2", "Phase 3", "Phase 4", "Phase 5"]:
            assert phase in body, f"Missing {phase}"

    def test_has_pitfall_prevention(self):
        _, body = _parse_agent_file()
        assert "Pitfall" in body or "pitfall" in body
        lower = body.lower()
        assert "gold-layer-only" in lower or "gold layer only" in lower

    def test_has_anti_patterns(self):
        _, body = _parse_agent_file()
        lower = body.lower()
        assert "no reconciliation" in lower or "missing reconciliation" in lower
        assert "alert threshold" in lower or "missing alert" in lower

    def test_references_skill_paths(self):
        _, body = _parse_agent_file()
        assert "create-dqs" in body
        assert "update-dqs" in body
        assert "validate-dqs" in body

    def test_references_generate_se_rules_skill(self):
        _, body = _parse_agent_file()
        assert "generate-se-rules" in body

    def test_enforces_readonly_database(self):
        _, body = _parse_agent_file()
        assert "-readonly" in body

    def test_references_memory_directory(self):
        _, body = _parse_agent_file()
        assert "dq-engineer-plugin/memory/" in body

    def test_instructs_ask_user_question(self):
        _, body = _parse_agent_file()
        assert "AskUserQuestion" in body

    def test_has_decision_documentation_format(self):
        _, body = _parse_agent_file()
        assert "Options Considered" in body or "Rationale" in body

    def test_references_dqs_sections(self):
        _, body = _parse_agent_file()
        assert "Overview" in body
        assert "Field-Level Validation Rules" in body
        assert "Referential Integrity" in body
        assert "Reconciliation" in body
        assert "Freshness" in body or "SLA" in body
        assert "Alert" in body or "Escalation" in body
        assert "Traceability" in body

    def test_has_severity_definitions(self):
        _, body = _parse_agent_file()
        assert "CRITICAL" in body
        assert "WARNING" in body
        assert "INFO" in body

    def test_has_rule_id_conventions(self):
        _, body = _parse_agent_file()
        assert "DQ-" in body

    def test_has_spark_expectations_knowledge(self):
        _, body = _parse_agent_file()
        lower = body.lower()
        assert "spark-expectations" in lower or "spark_expectations" in lower
        assert "row_dq" in body
        assert "agg_dq" in body
        assert "query_dq" in body

    def test_has_versioned_discovery(self):
        _, body = _parse_agent_file()
        assert "sort -V" in body

    def test_agent_has_subagent_fallback(self):
        """Agent must have fallback format for when AskUserQuestion is unavailable."""
        _, body = _parse_agent_file()
        assert "subagent" in body.lower() or "fallback" in body.lower()
        # Check for lettered options pattern
        assert "A)" in body or "A) " in body
