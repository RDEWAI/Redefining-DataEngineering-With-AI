"""Metadata API tools for PWI OpenHands agents.

This module provides tools for querying external metadata catalogs:
- query_metadata_catalog: Query data catalogs (Atlas, DataHub, OpenMetadata)
- get_lineage: Get data lineage information
- get_tags: Get data classification tags
"""

from __future__ import annotations

from typing import Any

from pwi.openhands.tools.base import create_tool, register_tool
from pwi.utils.logging import get_logger

logger = get_logger("openhands.tools.metadata")


# =============================================================================
# Tool Definitions
# =============================================================================

QueryMetadataCatalogTool = create_tool(
    name="query_metadata_catalog",
    description="Query an external metadata/data catalog API for entity information",
    parameters={
        "catalog_type": {
            "type": "string",
            "enum": ["atlas", "datahub", "openmetadata", "custom"],
            "description": "Type of metadata catalog to query",
        },
        "query_type": {
            "type": "string",
            "enum": ["search", "entity", "schema", "lineage", "tags"],
            "description": "Type of query to perform",
        },
        "entity_name": {
            "type": "string",
            "description": "Name of the entity to query (table, column, etc.)",
        },
        "catalog_url": {
            "type": "string",
            "description": "URL of the catalog API (optional, uses default if not provided)",
        },
    },
    required=["catalog_type", "query_type", "entity_name"],
)

GetLineageTool = create_tool(
    name="get_lineage",
    description="Get data lineage information for a table or column",
    parameters={
        "entity_name": {
            "type": "string",
            "description": "Name of the entity to get lineage for",
        },
        "direction": {
            "type": "string",
            "enum": ["upstream", "downstream", "both"],
            "description": "Direction of lineage to retrieve (default: both)",
        },
        "depth": {
            "type": "integer",
            "description": "How many levels of lineage to retrieve (default: 3)",
        },
    },
    required=["entity_name"],
)

GetTagsTool = create_tool(
    name="get_tags",
    description="Get data classification tags for an entity",
    parameters={
        "entity_name": {
            "type": "string",
            "description": "Name of the entity to get tags for",
        },
        "tag_types": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Types of tags to retrieve (e.g., 'pii', 'sensitive', 'classification')",
        },
    },
    required=["entity_name"],
)


# =============================================================================
# Tool Executors
# =============================================================================

def execute_query_metadata_catalog(
    catalog_type: str,
    query_type: str,
    entity_name: str,
    catalog_url: str | None = None,
) -> dict[str, Any]:
    """Query a metadata catalog.

    Args:
        catalog_type: Type of catalog (atlas, datahub, etc.).
        query_type: Type of query to perform.
        entity_name: Entity to query.
        catalog_url: Optional catalog URL.

    Returns:
        Query results dictionary.
    """
    logger.info(f"Querying {catalog_type} catalog for {entity_name} ({query_type})")

    # Note: In production, this would make actual API calls
    # For now, return mock data structure showing the expected format

    if catalog_type == "atlas":
        return _mock_atlas_response(query_type, entity_name)
    elif catalog_type == "datahub":
        return _mock_datahub_response(query_type, entity_name)
    elif catalog_type == "openmetadata":
        return _mock_openmetadata_response(query_type, entity_name)
    else:
        return {
            "success": False,
            "error": f"Unsupported catalog type: {catalog_type}",
            "supported_types": ["atlas", "datahub", "openmetadata"],
        }


def _mock_atlas_response(query_type: str, entity_name: str) -> dict[str, Any]:
    """Generate mock Atlas API response."""
    return {
        "success": True,
        "catalog": "atlas",
        "query_type": query_type,
        "entity_name": entity_name,
        "result": {
            "guid": f"atlas-{hash(entity_name) % 10000}",
            "typeName": "hive_table",
            "attributes": {
                "qualifiedName": entity_name,
                "name": entity_name.split(".")[-1] if "." in entity_name else entity_name,
                "description": f"Metadata for {entity_name}",
                "owner": "data_team",
                "createTime": 1704067200000,
            },
            "classifications": [
                {"typeName": "PII", "propagate": True},
            ],
        },
        "note": "Mock response - connect to actual Atlas API for real data",
    }


def _mock_datahub_response(query_type: str, entity_name: str) -> dict[str, Any]:
    """Generate mock DataHub API response."""
    return {
        "success": True,
        "catalog": "datahub",
        "query_type": query_type,
        "entity_name": entity_name,
        "result": {
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
        },
        "note": "Mock response - connect to actual DataHub API for real data",
    }


def _mock_openmetadata_response(query_type: str, entity_name: str) -> dict[str, Any]:
    """Generate mock OpenMetadata API response."""
    return {
        "success": True,
        "catalog": "openmetadata",
        "query_type": query_type,
        "entity_name": entity_name,
        "result": {
            "id": f"om-{hash(entity_name) % 10000}",
            "fullyQualifiedName": entity_name,
            "displayName": entity_name.split(".")[-1] if "." in entity_name else entity_name,
            "tableType": "Regular",
            "columns": [],
            "tags": [],
        },
        "note": "Mock response - connect to actual OpenMetadata API for real data",
    }


def execute_get_lineage(
    entity_name: str,
    direction: str = "both",
    depth: int = 3,
) -> dict[str, Any]:
    """Get data lineage information.

    Args:
        entity_name: Entity to get lineage for.
        direction: Lineage direction.
        depth: Levels of lineage.

    Returns:
        Lineage information dictionary.
    """
    logger.info(f"Getting {direction} lineage for {entity_name} (depth={depth})")

    # Mock lineage response
    return {
        "success": True,
        "entity_name": entity_name,
        "direction": direction,
        "depth": depth,
        "lineage": {
            "upstream": [
                {
                    "name": f"{entity_name}_source_1",
                    "type": "table",
                    "level": 1,
                },
                {
                    "name": f"{entity_name}_source_2",
                    "type": "table",
                    "level": 1,
                },
            ] if direction in ("upstream", "both") else [],
            "downstream": [
                {
                    "name": f"{entity_name}_derived_1",
                    "type": "table",
                    "level": 1,
                },
            ] if direction in ("downstream", "both") else [],
        },
        "note": "Mock response - connect to actual lineage service for real data",
    }


def execute_get_tags(
    entity_name: str,
    tag_types: list[str] | None = None,
) -> dict[str, Any]:
    """Get tags for an entity.

    Args:
        entity_name: Entity to get tags for.
        tag_types: Types of tags to retrieve.

    Returns:
        Tags dictionary.
    """
    logger.info(f"Getting tags for {entity_name}")

    # Mock tags response
    all_tags = {
        "pii": ["email", "phone_number", "ssn"],
        "sensitive": ["salary", "health_data"],
        "classification": ["internal", "confidential", "public"],
        "tier": ["gold", "silver", "bronze"],
    }

    filtered_tags = {}
    for tag_type in (tag_types or all_tags.keys()):
        if tag_type in all_tags:
            filtered_tags[tag_type] = all_tags[tag_type]

    return {
        "success": True,
        "entity_name": entity_name,
        "tags": filtered_tags,
        "note": "Mock response - connect to actual catalog for real tags",
    }


# =============================================================================
# Register Tools
# =============================================================================

def register_metadata_tools() -> None:
    """Register all metadata tools with the global registry."""
    register_tool(QueryMetadataCatalogTool, execute_query_metadata_catalog)
    register_tool(GetLineageTool, execute_get_lineage)
    register_tool(GetTagsTool, execute_get_tags)
    logger.info("Metadata tools registered")


# Auto-register on import
register_metadata_tools()
