"""Shape tests for the PR-lifecycle workflow templates embedded in
create-pipeline / update-pipeline / validate-pipeline SKILL.md.

These three workflows have no standalone YAML files yet — the templates
live inside SKILL.md, which is how `create-pipeline` emits them at
runtime. The tests assert the templates carry the load-bearing
conventions called out in the plan (always-teardown, shared driver
invocation, environment-gated prod).
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml


@pytest.fixture
def create_pipeline_md(plugin_root: Path) -> str:
    return (plugin_root / "skills" / "create-pipeline" / "SKILL.md").read_text(encoding="utf-8")


@pytest.fixture
def update_pipeline_md(plugin_root: Path) -> str:
    return (plugin_root / "skills" / "update-pipeline" / "SKILL.md").read_text(encoding="utf-8")


@pytest.fixture
def validate_pipeline_md(plugin_root: Path) -> str:
    return (plugin_root / "skills" / "validate-pipeline" / "SKILL.md").read_text(encoding="utf-8")


def _extract_yaml_blocks(markdown: str) -> dict[str, dict]:
    """Pull every ```yaml fenced block and parse it.

    Returns a mapping {first-non-blank-comment-or-name → parsed-yaml}.
    The create-pipeline templates are introduced by a bold filename
    header in markdown (e.g. **`_infra/ci/.github/workflows/pr-preview.yml`**),
    so we key by name from the parsed YAML and ignore unnamed blocks.
    """
    blocks: dict[str, dict] = {}
    for match in re.finditer(r"```yaml\n(.*?)```", markdown, re.DOTALL):
        raw = match.group(1)
        try:
            parsed = yaml.safe_load(raw)
        except yaml.YAMLError:
            continue
        if isinstance(parsed, dict) and "name" in parsed:
            blocks[parsed["name"]] = parsed
    return blocks


class TestCreatePipelineTemplates:
    def test_three_pr_lifecycle_workflows_present(self, create_pipeline_md: str) -> None:
        blocks = _extract_yaml_blocks(create_pipeline_md)
        assert "pr-preview" in blocks
        assert "sandbox-cleanup" in blocks
        assert "promote" in blocks

    def test_pr_preview_always_tears_down(self, create_pipeline_md: str) -> None:
        blocks = _extract_yaml_blocks(create_pipeline_md)
        steps = blocks["pr-preview"]["jobs"]["preview"]["steps"]
        # Find the teardown step.
        teardown = next(
            (s for s in steps if "down -v --remove-orphans" in str(s.get("run", ""))),
            None,
        )
        assert teardown is not None, "no teardown step in pr-preview.yml"
        assert teardown.get("if") == "always()", (
            "teardown must run unconditionally — `if: always()` is the only "
            "safe pattern. Without it, a failed test leaks named volumes "
            "onto the runner."
        )

    def test_sandbox_cleanup_uses_shared_driver(self, create_pipeline_md: str) -> None:
        blocks = _extract_yaml_blocks(create_pipeline_md)
        cleanup = blocks["sandbox-cleanup"]
        # Must trigger on pull_request closed.
        on = cleanup.get(True) or cleanup.get("on")  # yaml may parse `on:` as True
        if isinstance(on, dict) and "pull_request" in on:
            triggers = on["pull_request"].get("types", [])
            assert "closed" in triggers
        # Must call the shared driver script — never inline docker compose down.
        rendered = yaml.safe_dump(cleanup)
        assert "teardown_drivers/local_docker.sh" in rendered
        # Inline `docker compose down` in the cleanup workflow would defeat
        # the driver-as-single-source-of-truth contract.
        assert (
            "docker compose -f" not in rendered
            or "down -v" not in rendered.split("teardown_drivers")[0]
        )

    def test_promote_prod_is_environment_gated(self, create_pipeline_md: str) -> None:
        blocks = _extract_yaml_blocks(create_pipeline_md)
        prod_job = blocks["promote"]["jobs"]["promote-prod"]
        assert prod_job.get("environment") == "production", (
            "promote-prod must use a GitHub-environment gate with required "
            "reviewers — workflow_dispatch alone is not enough."
        )


class TestUpdatePipelineKnowsNewFiles:
    """update-pipeline must enumerate the three new filenames so its
    edit modes know to recognise them."""

    @pytest.mark.parametrize(
        "filename",
        ["pr-preview.yml", "sandbox-cleanup.yml", "promote.yml"],
    )
    def test_filename_mentioned(self, update_pipeline_md: str, filename: str) -> None:
        assert filename in update_pipeline_md, (
            f"{filename} must be listed in update-pipeline's recognised "
            "files table so edits can route to it."
        )

    def test_lists_load_bearing_invariants(self, update_pipeline_md: str) -> None:
        # The three "Hard rules" we added must stay in the skill so they
        # survive future SKILL.md edits.
        assert "if: always()" in update_pipeline_md
        assert "teardown_drivers" in update_pipeline_md
        assert "environment: production" in update_pipeline_md


class TestValidatePipelineCheckCoverage:
    """The CRITICAL checks added to validate-pipeline must explicitly call
    out the three new workflow files. Without that, the validator could
    silently approve a broken pr-preview / sandbox-cleanup / promote."""

    @pytest.mark.parametrize(
        "needle",
        [
            "pr-preview.yml",
            "sandbox-cleanup.yml",
            "promote.yml",
            "if: always()",
            "down -v --remove-orphans",
            "teardown_drivers",
            "environment: production",
        ],
    )
    def test_needle_present(self, validate_pipeline_md: str, needle: str) -> None:
        assert needle in validate_pipeline_md
