"""Artifact generation tools for PWI OpenHands agents using SDK pattern.

This module provides tools for generating and managing PWI artifacts:
- generate_artifact: Create a structured artifact
- save_artifact: Save artifact to file
- validate_artifact: Validate artifact format
- list_artifact_types: List available artifact types

Usage:
    from pwi.openhands.tools.artifact_tool import GenerateArtifactTool
    # Tools are auto-registered on import
"""

from __future__ import annotations

import csv
import io
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import Field

from openhands.sdk import Action, Observation
from openhands.sdk.llm import TextContent
from openhands.sdk.tool import ToolDefinition, ToolExecutor, register_tool

from pwi.utils.logging import get_logger

logger = get_logger("openhands.tools.artifact")


# Artifact types and their formats
ARTIFACT_TYPES = {
    "drd": {
        "format": "markdown",
        "extension": ".md",
        "name": "Data Requirements Document",
    },
    "pad": {
        "format": "markdown",
        "extension": ".md",
        "name": "Pipeline Architecture Document",
    },
    "dmd": {"format": "csv", "extension": ".csv", "name": "Data Mapping Document"},
    "dqs": {
        "format": "yaml",
        "extension": ".yaml",
        "name": "Data Quality Specification",
    },
    "stories": {"format": "markdown", "extension": ".md", "name": "User Stories"},
    "package": {
        "format": "markdown",
        "extension": ".md",
        "name": "Delivery Package",
    },
}

ArtifactType = Literal["drd", "pad", "dmd", "dqs", "stories", "package"]


# =============================================================================
# Generate Artifact Tool
# =============================================================================


class GenerateArtifactAction(Action):
    """Schema for artifact generation action."""

    artifact_type: ArtifactType = Field(description="Type of artifact to generate")
    content: str = Field(description="Content of the artifact")
    metadata: dict[str, Any] | None = Field(
        default=None, description="Additional metadata for the artifact"
    )


class GenerateArtifactObservation(Observation):
    """Schema for artifact generation result."""

    success: bool = Field(default=True)
    artifact: dict[str, Any] = Field(default_factory=dict)
    error: str | None = Field(default=None)


class GenerateArtifactExecutor(
    ToolExecutor[GenerateArtifactAction, GenerateArtifactObservation]
):
    """Executor for artifact generation."""

    def __call__(
        self, action: GenerateArtifactAction, conversation: Any = None
    ) -> GenerateArtifactObservation:
        """Execute artifact generation."""
        if action.artifact_type not in ARTIFACT_TYPES:
            error_msg = f"Unknown artifact type: {action.artifact_type}"
            return GenerateArtifactObservation(
                success=False,
                error=error_msg,
                content=[TextContent(text=f"Error: {error_msg}")],
            )

        type_info = ARTIFACT_TYPES[action.artifact_type]

        artifact = {
            "type": action.artifact_type,
            "name": type_info["name"],
            "format": type_info["format"],
            "extension": type_info["extension"],
            "content": action.content,
            "metadata": {
                "generated_at": datetime.utcnow().isoformat(),
                "version": "1.0",
                **(action.metadata or {}),
            },
        }

        logger.info(f"Generated {action.artifact_type} artifact")

        result_text = (
            f"Generated {type_info['name']} ({action.artifact_type})\n"
            f"Format: {type_info['format']}\n"
            f"Content length: {len(action.content)} chars"
        )
        return GenerateArtifactObservation(
            success=True,
            artifact=artifact,
            content=[TextContent(text=result_text)],
        )


class GenerateArtifactTool(
    ToolDefinition[GenerateArtifactAction, GenerateArtifactObservation]
):
    """Tool definition for artifact generation."""

    name = "generate_artifact"

    @classmethod
    def create(cls, conv_state: Any = None, **kwargs: Any) -> list[ToolDefinition]:
        """Create the tool instance."""
        return [
            cls(
                action_type=GenerateArtifactAction,
                observation_type=GenerateArtifactObservation,
                description="Create a structured PWI artifact with proper metadata",
                executor=GenerateArtifactExecutor(),
            )
        ]


# =============================================================================
# Save Artifact Tool
# =============================================================================


class SaveArtifactAction(Action):
    """Schema for artifact saving action."""

    artifact_type: ArtifactType = Field(description="Type of artifact")
    content: str = Field(description="Content to save")
    output_dir: str = Field(default="output", description="Output directory")
    session_id: str | None = Field(
        default=None, description="Session ID for organizing output"
    )


class SaveArtifactObservation(Observation):
    """Schema for artifact saving result."""

    success: bool = Field(default=True)
    file_path: str = Field(default="")
    artifact_type: str = Field(default="")
    size_bytes: int = Field(default=0)
    error: str | None = Field(default=None)


class SaveArtifactExecutor(ToolExecutor[SaveArtifactAction, SaveArtifactObservation]):
    """Executor for artifact saving."""

    def __call__(
        self, action: SaveArtifactAction, conversation: Any = None
    ) -> SaveArtifactObservation:
        """Execute artifact saving."""
        if action.artifact_type not in ARTIFACT_TYPES:
            error_msg = f"Unknown artifact type: {action.artifact_type}"
            return SaveArtifactObservation(
                success=False,
                error=error_msg,
                content=[TextContent(text=f"Error: {error_msg}")],
            )

        type_info = ARTIFACT_TYPES[action.artifact_type]

        # Build output path
        base_dir = Path(action.output_dir)
        if action.session_id:
            base_dir = base_dir / action.session_id

        base_dir.mkdir(parents=True, exist_ok=True)

        filename = f"{action.artifact_type}{type_info['extension']}"
        file_path = base_dir / filename

        try:
            file_path.write_text(action.content, encoding="utf-8")
            logger.info(f"Saved artifact to {file_path}")

            size_bytes = len(action.content.encode("utf-8"))
            result_text = (
                f"Saved {type_info['name']} ({action.artifact_type})\n"
                f"Path: {file_path}\n"
                f"Size: {size_bytes} bytes"
            )
            return SaveArtifactObservation(
                success=True,
                file_path=str(file_path),
                artifact_type=action.artifact_type,
                size_bytes=size_bytes,
                content=[TextContent(text=result_text)],
            )

        except Exception as e:
            logger.error(f"Failed to save artifact: {e}")
            return SaveArtifactObservation(
                success=False,
                error=str(e),
                content=[TextContent(text=f"Error saving artifact: {e}")],
            )


class SaveArtifactTool(ToolDefinition[SaveArtifactAction, SaveArtifactObservation]):
    """Tool definition for artifact saving."""

    name = "save_artifact"

    @classmethod
    def create(cls, conv_state: Any = None, **kwargs: Any) -> list[ToolDefinition]:
        """Create the tool instance."""
        return [
            cls(
                action_type=SaveArtifactAction,
                observation_type=SaveArtifactObservation,
                description="Save an artifact to a file in the output directory",
                executor=SaveArtifactExecutor(),
            )
        ]


# =============================================================================
# Validate Artifact Tool
# =============================================================================


class ValidateArtifactAction(Action):
    """Schema for artifact validation action."""

    artifact_type: ArtifactType = Field(description="Type of artifact to validate")
    content: str = Field(description="Content to validate")


class ValidateArtifactObservation(Observation):
    """Schema for artifact validation result."""

    success: bool = Field(default=True)
    valid: bool = Field(default=False)
    artifact_type: str = Field(default="")
    format: str = Field(default="")
    issues: list[str] = Field(default_factory=list)
    issue_count: int = Field(default=0)
    error: str | None = Field(default=None)


class ValidateArtifactExecutor(
    ToolExecutor[ValidateArtifactAction, ValidateArtifactObservation]
):
    """Executor for artifact validation."""

    def _validate_markdown(self, content: str, artifact_type: str) -> list[str]:
        """Validate markdown content."""
        issues = []

        # Check for expected headers based on artifact type
        expected_headers = {
            "drd": "# Data Requirements Document",
            "pad": "# Pipeline Architecture Document",
            "stories": "# User Stories",
            "package": "# Data Engineering Delivery Package",
        }

        if artifact_type in expected_headers:
            if expected_headers[artifact_type] not in content:
                issues.append(
                    f"Missing expected header: {expected_headers[artifact_type]}"
                )

        # Check for code fence wrapping (should not be wrapped)
        if content.strip().startswith("```markdown"):
            issues.append("Content should not be wrapped in ```markdown code fences")

        # Check for ASCII art (should use Mermaid)
        ascii_chars = ["┌", "─", "┐", "│", "└", "┘", "►", "▶"]
        for char in ascii_chars:
            if char in content:
                issues.append(
                    f"ASCII art character found: '{char}' - use Mermaid diagrams instead"
                )
                break

        return issues

    # Expected DMD columns (13 columns in exact order, including layer)
    DMD_EXPECTED_COLUMNS = [
        "source_system",
        "source_table",
        "source_column",
        "source_type",
        "target_table",
        "target_column",
        "target_type",
        "transformation",
        "business_rule",
        "nullable",
        "default_value",
        "notes",
        "layer",  # Required: bronze, silver, or gold
    ]

    # Valid layer values
    VALID_LAYERS = {"bronze", "silver", "gold"}

    def _validate_csv(self, content: str, artifact_type: str = "dmd") -> list[str]:
        """Validate CSV content."""
        issues = []
        content_stripped = content.strip()

        # CRITICAL: Check if content is markdown instead of CSV
        if content_stripped.startswith("#") or content_stripped.startswith("## "):
            issues.append(
                "CRITICAL: Content is markdown prose, not CSV. "
                "Expected raw CSV starting with header row: source_system,source_table,..."
            )
            return issues  # Don't continue if completely wrong format

        # Check for code fence wrapping (should not be wrapped)
        if content_stripped.startswith("```csv") or content_stripped.startswith("```"):
            issues.append("Content should not be wrapped in ```csv code fences - output raw CSV only")

        # Check for preamble text before CSV
        lines = content_stripped.split("\n")
        if lines and not lines[0].startswith(("source_", "target_", '"')):
            # First line doesn't look like CSV header
            first_line = lines[0][:50] + "..." if len(lines[0]) > 50 else lines[0]
            if "," not in lines[0] or any(
                word in lines[0].lower() for word in ["here is", "document", "mapping document", "below"]
            ):
                issues.append(f"CSV should start with header row, not preamble text: '{first_line}'")

        try:
            reader = csv.reader(io.StringIO(content))
            rows = list(reader)

            if not rows:
                issues.append("CSV is empty")
            elif len(rows) == 1:
                issues.append("CSV has only header row, no data")

            # Check for consistent column count
            if rows:
                expected_cols = len(rows[0])
                for i, row in enumerate(rows[1:], 2):
                    if len(row) != expected_cols:
                        issues.append(
                            f"Row {i} has {len(row)} columns, expected {expected_cols}"
                        )
                        break

            # DMD-specific: Check expected columns
            if artifact_type == "dmd" and rows:
                header = [col.strip().lower() for col in rows[0]]
                expected_lower = [col.lower() for col in self.DMD_EXPECTED_COLUMNS]

                if header != expected_lower:
                    issues.append(
                        f"DMD header mismatch. Expected 13 columns in this order: {self.DMD_EXPECTED_COLUMNS}"
                    )
                    issues.append(f"Got {len(header)} columns: {rows[0]}")

                # Check that header starts with source_system (not target_table)
                if header and header[0] != "source_system":
                    issues.append(
                        f"DMD header must start with 'source_system', not '{rows[0][0]}'"
                    )

                # Check that last column is 'layer'
                if header and header[-1] != "layer":
                    issues.append(
                        f"DMD header must end with 'layer' column, not '{rows[0][-1]}'"
                    )

                # Validate layer column values
                if len(rows) > 1 and len(header) >= 13:
                    layer_idx = 12  # 0-indexed, 13th column
                    invalid_layers = []
                    for i, row in enumerate(rows[1:], 2):
                        if len(row) > layer_idx:
                            layer = row[layer_idx].strip().lower()
                            if layer and layer not in self.VALID_LAYERS:
                                invalid_layers.append((i, layer))
                                if len(invalid_layers) >= 3:  # Only report first 3
                                    break

                    for row_num, layer_val in invalid_layers:
                        issues.append(
                            f"Row {row_num}: Invalid layer value '{layer_val}' - must be bronze, silver, or gold"
                        )

        except csv.Error as e:
            issues.append(f"Invalid CSV format: {e}")

        return issues

    def _validate_yaml(self, content: str) -> list[str]:
        """Validate YAML content."""
        issues = []
        content_stripped = content.strip()

        # CRITICAL: Check if content is markdown instead of YAML
        if content_stripped.startswith("#") and not content_stripped.startswith("# "):
            # YAML comments start with # but markdown headers have # followed by space
            pass
        elif content_stripped.startswith("# ") or content_stripped.startswith("## "):
            issues.append(
                "CRITICAL: Content appears to be markdown prose, not YAML. "
                "Expected YAML starting with 'version:' key."
            )
            return issues

        # Check for code fence wrapping
        if content_stripped.startswith("```yaml") or content_stripped.startswith("```"):
            issues.append("Content should not be wrapped in ```yaml code fences - output raw YAML only")

        # Check for leading 'yaml' text (from code fence artifact)
        if content_stripped.lower().startswith("yaml\n") or content_stripped.lower().startswith("yaml "):
            issues.append("Content starts with 'yaml' text - remove code fence artifacts")

        try:
            data = yaml.safe_load(content)
            if data is None:
                issues.append("YAML is empty or invalid")
            elif isinstance(data, dict):
                # DQS-specific: Check for expected top-level keys
                if "version" not in data:
                    issues.append("DQS YAML should have 'version' key at top level")
                if "quality_dimensions" not in data and "quality_rules" not in data:
                    issues.append("DQS YAML should have 'quality_dimensions' or 'quality_rules' section")
        except yaml.YAMLError as e:
            issues.append(f"Invalid YAML format: {e}")

        return issues

    def __call__(
        self, action: ValidateArtifactAction, conversation: Any = None
    ) -> ValidateArtifactObservation:
        """Execute artifact validation."""
        if action.artifact_type not in ARTIFACT_TYPES:
            error_msg = f"Unknown artifact type: {action.artifact_type}"
            return ValidateArtifactObservation(
                success=False,
                valid=False,
                error=error_msg,
                content=[TextContent(text=f"Error: {error_msg}")],
            )

        type_info = ARTIFACT_TYPES[action.artifact_type]
        issues: list[str] = []

        # Validate based on format
        if type_info["format"] == "markdown":
            issues.extend(self._validate_markdown(action.content, action.artifact_type))
        elif type_info["format"] == "csv":
            issues.extend(self._validate_csv(action.content, action.artifact_type))
        elif type_info["format"] == "yaml":
            issues.extend(self._validate_yaml(action.content))

        # Build text result for content field
        is_valid = len(issues) == 0
        result_lines = [
            f"Validation Result for {action.artifact_type.upper()} ({type_info['format']})",
            f"Status: {'VALID' if is_valid else 'INVALID'}",
            f"Issues found: {len(issues)}",
        ]
        if issues:
            result_lines.append("\nIssues:")
            for i, issue in enumerate(issues, 1):
                result_lines.append(f"  {i}. {issue}")

        return ValidateArtifactObservation(
            success=True,
            valid=is_valid,
            artifact_type=action.artifact_type,
            format=type_info["format"],
            issues=issues,
            issue_count=len(issues),
            content=[TextContent(text="\n".join(result_lines))],
        )


class ValidateArtifactTool(
    ToolDefinition[ValidateArtifactAction, ValidateArtifactObservation]
):
    """Tool definition for artifact validation."""

    name = "validate_artifact"

    @classmethod
    def create(cls, conv_state: Any = None, **kwargs: Any) -> list[ToolDefinition]:
        """Create the tool instance."""
        return [
            cls(
                action_type=ValidateArtifactAction,
                observation_type=ValidateArtifactObservation,
                description="Validate an artifact's format and structure",
                executor=ValidateArtifactExecutor(),
            )
        ]


# =============================================================================
# List Artifact Types Tool
# =============================================================================


class ListArtifactTypesAction(Action):
    """Schema for listing artifact types action."""

    pass  # No parameters needed


class ListArtifactTypesObservation(Observation):
    """Schema for listing artifact types result."""

    success: bool = Field(default=True)
    artifact_types: dict[str, dict[str, str]] = Field(default_factory=dict)
    count: int = Field(default=0)


class ListArtifactTypesExecutor(
    ToolExecutor[ListArtifactTypesAction, ListArtifactTypesObservation]
):
    """Executor for listing artifact types."""

    def __call__(
        self, action: ListArtifactTypesAction, conversation: Any = None
    ) -> ListArtifactTypesObservation:
        """Execute artifact types listing."""
        # Build text representation
        lines = [f"Available PWI Artifact Types ({len(ARTIFACT_TYPES)}):", ""]
        for atype, info in ARTIFACT_TYPES.items():
            lines.append(f"  - {atype}: {info['name']} ({info['format']}, {info['extension']})")

        return ListArtifactTypesObservation(
            success=True,
            artifact_types=ARTIFACT_TYPES,
            count=len(ARTIFACT_TYPES),
            content=[TextContent(text="\n".join(lines))],
        )


class ListArtifactTypesTool(
    ToolDefinition[ListArtifactTypesAction, ListArtifactTypesObservation]
):
    """Tool definition for listing artifact types."""

    name = "list_artifact_types"

    @classmethod
    def create(cls, conv_state: Any = None, **kwargs: Any) -> list[ToolDefinition]:
        """Create the tool instance."""
        return [
            cls(
                action_type=ListArtifactTypesAction,
                observation_type=ListArtifactTypesObservation,
                description="List all available PWI artifact types and their formats",
                executor=ListArtifactTypesExecutor(),
            )
        ]


# =============================================================================
# Register Tools with SDK
# =============================================================================


def _register_artifact_tools() -> None:
    """Register all artifact tools with the OpenHands SDK registry."""
    register_tool("generate_artifact", GenerateArtifactTool)
    register_tool("save_artifact", SaveArtifactTool)
    register_tool("validate_artifact", ValidateArtifactTool)
    register_tool("list_artifact_types", ListArtifactTypesTool)
    logger.info("Artifact tools registered with OpenHands SDK")


# Auto-register on import
_register_artifact_tools()


__all__ = [
    "ARTIFACT_TYPES",
    "GenerateArtifactAction",
    "GenerateArtifactObservation",
    "GenerateArtifactTool",
    "SaveArtifactAction",
    "SaveArtifactObservation",
    "SaveArtifactTool",
    "ValidateArtifactAction",
    "ValidateArtifactObservation",
    "ValidateArtifactTool",
    "ListArtifactTypesAction",
    "ListArtifactTypesObservation",
    "ListArtifactTypesTool",
]
