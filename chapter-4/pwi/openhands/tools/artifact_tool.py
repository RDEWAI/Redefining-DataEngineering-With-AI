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
            return GenerateArtifactObservation(
                success=False,
                error=f"Unknown artifact type: {action.artifact_type}",
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

        return GenerateArtifactObservation(success=True, artifact=artifact)


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
            return SaveArtifactObservation(
                success=False, error=f"Unknown artifact type: {action.artifact_type}"
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

            return SaveArtifactObservation(
                success=True,
                file_path=str(file_path),
                artifact_type=action.artifact_type,
                size_bytes=len(action.content.encode("utf-8")),
            )

        except Exception as e:
            logger.error(f"Failed to save artifact: {e}")
            return SaveArtifactObservation(success=False, error=str(e))


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

    # Expected DMD columns (12 columns in exact order)
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
    ]

    def _validate_csv(self, content: str, artifact_type: str = "dmd") -> list[str]:
        """Validate CSV content."""
        issues = []

        # Check for code fence wrapping (should not be wrapped)
        if content.strip().startswith("```csv") or content.strip().startswith("```"):
            issues.append("Content should not be wrapped in ```csv code fences - output raw CSV only")

        # Check for preamble text before CSV
        lines = content.strip().split("\n")
        if lines and not lines[0].startswith(("source_", "target_", '"')):
            # First line doesn't look like CSV header
            first_line = lines[0][:50] + "..." if len(lines[0]) > 50 else lines[0]
            if not "," in lines[0] or any(
                word in lines[0].lower() for word in ["here", "document", "mapping", "data"]
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
                header = rows[0]
                if header != self.DMD_EXPECTED_COLUMNS:
                    issues.append(
                        f"DMD header mismatch. Expected 12 columns: {self.DMD_EXPECTED_COLUMNS}"
                    )
                    issues.append(f"Got {len(header)} columns: {header}")

        except csv.Error as e:
            issues.append(f"Invalid CSV format: {e}")

        return issues

    def _validate_yaml(self, content: str) -> list[str]:
        """Validate YAML content."""
        issues = []

        try:
            data = yaml.safe_load(content)
            if data is None:
                issues.append("YAML is empty or invalid")
        except yaml.YAMLError as e:
            issues.append(f"Invalid YAML format: {e}")

        return issues

    def __call__(
        self, action: ValidateArtifactAction, conversation: Any = None
    ) -> ValidateArtifactObservation:
        """Execute artifact validation."""
        if action.artifact_type not in ARTIFACT_TYPES:
            return ValidateArtifactObservation(
                success=False,
                valid=False,
                error=f"Unknown artifact type: {action.artifact_type}",
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

        return ValidateArtifactObservation(
            success=True,
            valid=len(issues) == 0,
            artifact_type=action.artifact_type,
            format=type_info["format"],
            issues=issues,
            issue_count=len(issues),
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
        return ListArtifactTypesObservation(
            success=True,
            artifact_types=ARTIFACT_TYPES,
            count=len(ARTIFACT_TYPES),
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
