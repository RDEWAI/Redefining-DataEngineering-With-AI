"""Tests for the architect agent definition file structure and content.

The agent is a slim routing layer that delegates to skills. Detailed workflow
content (elicitation protocol, pitfall prevention, etc.) lives in skills and
is tested in test_skill_frontmatter.py / test_skill_evals.py.
"""

from __future__ import annotations

from pathlib import Path

import yaml

AGENT_FILE = (
    Path(__file__).resolve().parent.parent
    / "architect-plugin"
    / "agents"
    / "architect-agent.REFERENCE.md"
)

SKILL_DIR = Path(__file__).resolve().parent.parent / "architect-plugin" / "skills"


def _parse_agent_file() -> tuple[dict, str]:
    """Parse the agent REFERENCE file into frontmatter and body.

    REFERENCE files have their YAML frontmatter wrapped in <!-- --> comments.
    This parser strips the comment markers before parsing.
    """
    raw = AGENT_FILE.read_text(encoding="utf-8")
    # Strip HTML comment markers around frontmatter
    content = raw.replace("<!-- ---", "---").rstrip()
    if content.endswith("-->"):
        content = content[: -len("-->")].rstrip()
    assert content.startswith("---"), "Must start with YAML frontmatter (or <!-- ---)"

    parts = content.split("---", 2)
    assert len(parts) >= 3, "Must have --- delimited frontmatter"

    frontmatter = yaml.safe_load(parts[1])
    body = parts[2]
    return frontmatter, body


def _parse_skill_file(skill_name: str) -> tuple[dict, str]:
    """Parse a skill markdown file into frontmatter and body."""
    skill_file = SKILL_DIR / skill_name / "SKILL.md"
    content = skill_file.read_text(encoding="utf-8")
    parts = content.split("---", 2)
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
    """YAML frontmatter must contain required fields with correct values."""

    def test_name_is_architect_agent(self):
        fm, _ = _parse_agent_file()
        assert fm["name"] == "architect-agent"

    def test_model_is_inherit(self):
        fm, _ = _parse_agent_file()
        assert fm["model"] == "inherit"

    def test_has_description(self):
        fm, _ = _parse_agent_file()
        assert "description" in fm
        assert len(fm["description"]) > 50, "Description should be detailed"

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
    """The agent body must contain routing, behavioral rules, and skill references."""

    def test_references_all_skills(self):
        _, body = _parse_agent_file()
        assert "create-hld" in body
        assert "update-hld" in body
        assert "validate-hld" in body

    def test_has_skills_delegation_statement(self):
        """Agent must state that skills own the workflow."""
        _, body = _parse_agent_file()
        assert "skill" in body.lower()
        assert "delegate" in body.lower() or "workflow" in body.lower()

    def test_has_behavioral_rules(self):
        """Agent must have cross-cutting behavioral rules."""
        _, body = _parse_agent_file()
        assert "Behavioral Rules" in body or "behavioral rules" in body

    def test_enforces_readonly_database(self):
        _, body = _parse_agent_file()
        assert "-readonly" in body

    def test_has_traceability_enforcement(self):
        _, body = _parse_agent_file()
        assert "trace" in body.lower()
        assert "DRD" in body

    def test_enforces_user_confirmation(self):
        _, body = _parse_agent_file()
        assert "confirmation" in body.lower() or "confirm" in body.lower()

    def test_instructs_ask_user_question(self):
        _, body = _parse_agent_file()
        assert "AskUserQuestion" in body

    def test_agent_has_subagent_fallback(self):
        """Agent must have fallback format for when AskUserQuestion is unavailable."""
        _, body = _parse_agent_file()
        assert "subagent" in body.lower() or "fallback" in body.lower()
        assert "A)" in body or "A) " in body


class TestSkillsContainAgentWorkflow:
    """Skills must contain the detailed workflow that was moved from the agent.

    This ensures no content was lost during the agent-to-skill migration.
    """

    # --- create-hld ---

    def test_create_hld_has_elicitation_protocol(self):
        _, body = _parse_skill_file("create-hld")
        assert "Elicitation Protocol" in body

    def test_create_hld_has_four_responsibilities(self):
        _, body = _parse_skill_file("create-hld")
        assert "Architecture Pattern Selection" in body
        assert "Technology Selection" in body
        assert "Layer Design" in body
        assert "Non-Functional Requirements" in body or "Scalability & Capacity" in body

    def test_create_hld_has_workflow_phases(self):
        _, body = _parse_skill_file("create-hld")
        for phase in ["Phase 1", "Phase 2", "Phase 3", "Phase 4", "Phase 5"]:
            assert phase in body, f"create-hld missing {phase}"

    def test_create_hld_has_pitfall_prevention(self):
        _, body = _parse_skill_file("create-hld")
        assert "Pitfall" in body
        assert "Over-Engineering" in body
        assert "Skipping Data Exploration" in body
        assert "Missing DRD Traceability" in body

    def test_create_hld_has_anti_patterns(self):
        _, body = _parse_skill_file("create-hld")
        assert "Anti-Pattern" in body or "Anti-pattern" in body

    def test_create_hld_has_db_gate(self):
        _, body = _parse_skill_file("create-hld")
        assert "-readonly" in body
        assert "STOP" in body or "Do NOT proceed" in body

    def test_create_hld_has_versioned_discovery(self):
        _, body = _parse_skill_file("create-hld")
        assert "sort -V" in body

    def test_create_hld_has_session_memory(self):
        _, body = _parse_skill_file("create-hld")
        assert "memory/hld/" in body

    def test_create_hld_has_decision_documentation(self):
        _, body = _parse_skill_file("create-hld")
        assert "Options Considered" in body
        assert "Rationale" in body
        assert "Trade-off" in body

    def test_create_hld_has_writing_style(self):
        _, body = _parse_skill_file("create-hld")
        assert "Writing Style" in body
        assert "High-level over implementation" in body

    def test_create_hld_has_hld_sections_reference(self):
        _, body = _parse_skill_file("create-hld")
        assert "HLD Sections Reference" in body or "Section Guide" in body
        assert "Executive Summary" in body
        assert "Data Architecture" in body
        assert "Technology Decisions" in body

    # --- update-hld ---

    def test_update_hld_has_elicitation_protocol(self):
        _, body = _parse_skill_file("update-hld")
        assert "Elicitation Protocol" in body

    def test_update_hld_has_workflow_phases(self):
        _, body = _parse_skill_file("update-hld")
        for phase in ["Phase 1", "Phase 2", "Phase 3", "Phase 4", "Phase 5"]:
            assert phase in body, f"update-hld missing {phase}"

    def test_update_hld_has_pitfall_prevention(self):
        _, body = _parse_skill_file("update-hld")
        assert "Pitfall" in body
        assert "Over-Engineering" in body
        assert "Skipping Data Exploration" in body
        assert "Missing DRD Traceability" in body

    def test_update_hld_has_session_memory(self):
        _, body = _parse_skill_file("update-hld")
        assert "memory/hld/" in body

    def test_update_hld_has_cross_section_consistency(self):
        _, body = _parse_skill_file("update-hld")
        assert "consistency" in body.lower() or "cross-section" in body.lower()
