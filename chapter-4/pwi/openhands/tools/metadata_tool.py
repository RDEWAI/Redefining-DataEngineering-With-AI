"""Metadata API tools for PWI OpenHands agents using SDK pattern.

This module provides tools for querying external metadata catalogs:
- query_metadata_catalog: Query data catalogs (Atlas, DataHub, OpenMetadata)
- get_lineage: Get data lineage information
- get_tags: Get data classification tags

Usage:
    from pwi.openhands.tools.metadata_tool import QueryMetadataCatalogTool
    # Tools are auto-registered on import
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import Field

from openhands.sdk import Action, Observation
from openhands.sdk.tool import ToolDefinition, ToolExecutor, register_tool

from pwi.utils.logging import get_logger

logger = get_logger("openhands.tools.metadata")


# =============================================================================
# Query Metadata Catalog Tool
# =============================================================================


class QueryMetadataCatalogAction(Action):
    """Schema for metadata catalog query action."""

    catalog_type: Literal["atlas", "datahub", "openmetadata", "custom"] = Field(
        description="Type of metadata catalog to query"
    )
    query_type: Literal["search", "entity", "schema", "lineage", "tags"] = Field(
        description="Type of query to perform"
    )
    entity_name: str = Field(
        description="Name of the entity to query (table, column, etc.)"
    )
    catalog_url: str | None = Field(
        default=None,
        description="URL of the catalog API (optional, uses default if not provided)",
    )


class QueryMetadataCatalogObservation(Observation):
    """Schema for metadata catalog query result."""

    success: bool = Field(default=True)
    catalog: str = Field(default="")
    query_type: str = Field(default="")
    entity_name: str = Field(default="")
    result: dict[str, Any] = Field(default_factory=dict)
    error: str | None = Field(default=None)
    note: str | None = Field(default=None)


class QueryMetadataCatalogExecutor(
    ToolExecutor[QueryMetadataCatalogAction, QueryMetadataCatalogObservation]
):
    """Executor for metadata catalog queries."""

    def _mock_atlas_response(
        self, query_type: str, entity_name: str
    ) -> dict[str, Any]:
        """Generate mock Atlas API response."""
        return {
            "guid": f"atlas-{hash(entity_name) % 10000}",
            "typeName": "hive_table",
            "attributes": {
                "qualifiedName": entity_name,
                "name": (
                    entity_name.split(".")[-1] if "." in entity_name else entity_name
                ),
                "description": f"Metadata for {entity_name}",
                "owner": "data_team",
                "createTime": 1704067200000,
            },
            "classifications": [
                {"typeName": "PII", "propagate": True},
            ],
        }

    def _mock_datahub_response(
        self, query_type: str, entity_name: str
    ) -> dict[str, Any]:
        """Generate mock DataHub API response."""
        return {
            "urn": f"urn:li:dataset:(urn:li:dataPlatform:duckdb,{entity_name},PROD)",
            "aspects": {
                "datasetProperties": {
                    "name": entity_name,
                    "description": f"Dataset {entity_name}",
                },
                "schemaMetadata": {
                    "platform": "urn:li:dataPlatform:duckdb",
                    "fields": [],
                },
            },
            "tags": ["tier:gold"],
        }

    def _mock_openmetadata_response(
        self, query_type: str, entity_name: str
    ) -> dict[str, Any]:
        """Generate mock OpenMetadata API response."""
        return {
            "id": f"om-{hash(entity_name) % 10000}",
            "fullyQualifiedName": entity_name,
            "displayName": (
                entity_name.split(".")[-1] if "." in entity_name else entity_name
            ),
            "tableType": "Regular",
            "columns": [],
            "tags": [],
        }

    def __call__(
        self, action: QueryMetadataCatalogAction, conversation: Any = None
    ) -> QueryMetadataCatalogObservation:
        """Execute metadata catalog query."""
        logger.info(
            f"Querying {action.catalog_type} catalog for "
            f"{action.entity_name} ({action.query_type})"
        )

        # Note: In production, this would make actual API calls
        # For now, return mock data structure showing the expected format

        if action.catalog_type == "atlas":
            result = self._mock_atlas_response(action.query_type, action.entity_name)
        elif action.catalog_type == "datahub":
            result = self._mock_datahub_response(action.query_type, action.entity_name)
        elif action.catalog_type == "openmetadata":
            result = self._mock_openmetadata_response(
                action.query_type, action.entity_name
            )
        else:
            return QueryMetadataCatalogObservation(
                success=False,
                error=f"Unsupported catalog type: {action.catalog_type}",
                note="Supported types: atlas, datahub, openmetadata",
            )

        return QueryMetadataCatalogObservation(
            success=True,
            catalog=action.catalog_type,
            query_type=action.query_type,
            entity_name=action.entity_name,
            result=result,
            note="Mock response - connect to actual catalog API for real data",
        )


class QueryMetadataCatalogTool(
    ToolDefinition[QueryMetadataCatalogAction, QueryMetadataCatalogObservation]
):
    """Tool definition for metadata catalog queries."""

    name = "query_metadata_catalog"

    @classmethod
    def create(cls, conv_state: Any = None, **kwargs: Any) -> list[ToolDefinition]:
        """Create the tool instance."""
        return [
            cls(
                action_type=QueryMetadataCatalogAction,
                observation_type=QueryMetadataCatalogObservation,
                description="Query an external metadata/data catalog API for entity information",
                executor=QueryMetadataCatalogExecutor(),
            )
        ]


# =============================================================================
# Get Lineage Tool
# =============================================================================


class GetLineageAction(Action):
    """Schema for lineage query action."""

    entity_name: str = Field(description="Name of the entity to get lineage for")
    direction: Literal["upstream", "downstream", "both"] = Field(
        default="both", description="Direction of lineage to retrieve"
    )
    depth: int = Field(default=3, description="How many levels of lineage to retrieve")


class GetLineageObservation(Observation):
    """Schema for lineage query result."""

    success: bool = Field(default=True)
    entity_name: str = Field(default="")
    direction: str = Field(default="")
    depth: int = Field(default=0)
    lineage: dict[str, list[dict[str, Any]]] = Field(default_factory=dict)
    error: str | None = Field(default=None)
    note: str | None = Field(default=None)


class GetLineageExecutor(ToolExecutor[GetLineageAction, GetLineageObservation]):
    """Executor for lineage queries."""

    def __call__(
        self, action: GetLineageAction, conversation: Any = None
    ) -> GetLineageObservation:
        """Execute lineage query."""
        logger.info(
            f"Getting {action.direction} lineage for "
            f"{action.entity_name} (depth={action.depth})"
        )

        # Mock lineage response
        upstream = []
        downstream = []

        if action.direction in ("upstream", "both"):
            upstream = [
                {
                    "name": f"{action.entity_name}_source_1",
                    "type": "table",
                    "level": 1,
                },
                {
                    "name": f"{action.entity_name}_source_2",
                    "type": "table",
                    "level": 1,
                },
            ]

        if action.direction in ("downstream", "both"):
            downstream = [
                {
                    "name": f"{action.entity_name}_derived_1",
                    "type": "table",
                    "level": 1,
                },
            ]

        return GetLineageObservation(
            success=True,
            entity_name=action.entity_name,
            direction=action.direction,
            depth=action.depth,
            lineage={"upstream": upstream, "downstream": downstream},
            note="Mock response - connect to actual lineage service for real data",
        )


class GetLineageTool(ToolDefinition[GetLineageAction, GetLineageObservation]):
    """Tool definition for lineage queries."""

    name = "get_lineage"

    @classmethod
    def create(cls, conv_state: Any = None, **kwargs: Any) -> list[ToolDefinition]:
        """Create the tool instance."""
        return [
            cls(
                action_type=GetLineageAction,
                observation_type=GetLineageObservation,
                description="Get data lineage information for a table or column",
                executor=GetLineageExecutor(),
            )
        ]


# =============================================================================
# Get Tags Tool
# =============================================================================


class GetTagsAction(Action):
    """Schema for tags query action."""

    entity_name: str = Field(description="Name of the entity to get tags for")
    tag_types: list[str] | None = Field(
        default=None,
        description="Types of tags to retrieve (e.g., 'pii', 'sensitive', 'classification')",
    )


class GetTagsObservation(Observation):
    """Schema for tags query result."""

    success: bool = Field(default=True)
    entity_name: str = Field(default="")
    tags: dict[str, list[str]] = Field(default_factory=dict)
    error: str | None = Field(default=None)
    note: str | None = Field(default=None)


class GetTagsExecutor(ToolExecutor[GetTagsAction, GetTagsObservation]):
    """Executor for tags queries."""

    def __call__(
        self, action: GetTagsAction, conversation: Any = None
    ) -> GetTagsObservation:
        """Execute tags query."""
        logger.info(f"Getting tags for {action.entity_name}")

        # Mock tags response
        all_tags = {
            "pii": ["email", "phone_number", "ssn"],
            "sensitive": ["salary", "health_data"],
            "classification": ["internal", "confidential", "public"],
            "tier": ["gold", "silver", "bronze"],
        }

        filtered_tags = {}
        for tag_type in action.tag_types or all_tags.keys():
            if tag_type in all_tags:
                filtered_tags[tag_type] = all_tags[tag_type]

        return GetTagsObservation(
            success=True,
            entity_name=action.entity_name,
            tags=filtered_tags,
            note="Mock response - connect to actual catalog for real tags",
        )


class GetTagsTool(ToolDefinition[GetTagsAction, GetTagsObservation]):
    """Tool definition for tags queries."""

    name = "get_tags"

    @classmethod
    def create(cls, conv_state: Any = None, **kwargs: Any) -> list[ToolDefinition]:
        """Create the tool instance."""
        return [
            cls(
                action_type=GetTagsAction,
                observation_type=GetTagsObservation,
                description="Get data classification tags for an entity",
                executor=GetTagsExecutor(),
            )
        ]


# =============================================================================
# Register Tools with SDK
# =============================================================================


def _register_metadata_tools() -> None:
    """Register all metadata tools with the OpenHands SDK registry."""
    register_tool("query_metadata_catalog", QueryMetadataCatalogTool)
    register_tool("get_lineage", GetLineageTool)
    register_tool("get_tags", GetTagsTool)
    logger.info("Metadata tools registered with OpenHands SDK")


# Auto-register on import
_register_metadata_tools()


__all__ = [
    "QueryMetadataCatalogAction",
    "QueryMetadataCatalogObservation",
    "QueryMetadataCatalogTool",
    "GetLineageAction",
    "GetLineageObservation",
    "GetLineageTool",
    "GetTagsAction",
    "GetTagsObservation",
    "GetTagsTool",
]
