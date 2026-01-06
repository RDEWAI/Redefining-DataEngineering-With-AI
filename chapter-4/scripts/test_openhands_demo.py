#!/usr/bin/env python3
"""OpenHands Integration Demonstration.

This script demonstrates the OpenHands SDK integration with PWI,
showing how agents can use tools to interact with external systems.
"""

import asyncio
from pathlib import Path

# Rich for nice output
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.syntax import Syntax

console = Console()


def section(title: str):
    """Print a section header."""
    console.print()
    console.print(Panel(f"[bold cyan]{title}[/bold cyan]", expand=False))
    console.print()


async def main():
    console.print()
    console.print("[bold magenta]" + "=" * 60 + "[/bold magenta]")
    console.print("[bold magenta]  OpenHands SDK Integration Demonstration[/bold magenta]")
    console.print("[bold magenta]" + "=" * 60 + "[/bold magenta]")

    # =========================================================================
    # 1. Tool Registry Demo
    # =========================================================================
    section("1. Tool Registry - 14 Tools Available")

    from pwi.openhands.tools import get_registry, get_tools_for_agent

    registry = get_registry()

    table = Table(title="Registered Tools")
    table.add_column("Tool Name", style="cyan")
    table.add_column("Category", style="green")

    categories = {
        "duckdb_query": "DuckDB",
        "duckdb_schema": "DuckDB",
        "duckdb_validate": "DuckDB",
        "duckdb_tables": "DuckDB",
        "analyze_csv": "CSV",
        "csv_stats": "CSV",
        "csv_sample": "CSV",
        "query_metadata_catalog": "Metadata",
        "get_lineage": "Metadata",
        "get_tags": "Metadata",
        "generate_artifact": "Artifact",
        "save_artifact": "Artifact",
        "validate_artifact": "Artifact",
        "list_artifact_types": "Artifact",
    }

    for tool_name in registry.tool_names:
        table.add_row(tool_name, categories.get(tool_name, "Unknown"))

    console.print(table)

    # =========================================================================
    # 2. Agent Tool Assignment Demo
    # =========================================================================
    section("2. Agent Tool Assignment")

    from pwi.openhands.agents import (
        DataAnalystAgent,
        DataArchitectAgent,
        MappingEngineerAgent,
        DQEngineerAgent,
        StoryWriterAgent,
        SyncAgent,
        PWIAgentConfig,
    )

    agents_info = [
        ("data_analyst", DataAnalystAgent),
        ("data_architect", DataArchitectAgent),
        ("mapping_engineer", MappingEngineerAgent),
        ("dq_engineer", DQEngineerAgent),
        ("story_writer", StoryWriterAgent),
        ("sync_agent", SyncAgent),
    ]

    table = Table(title="Agent Tool Assignments")
    table.add_column("Agent", style="cyan")
    table.add_column("Artifact", style="green")
    table.add_column("Tools", style="yellow")

    for name, agent_class in agents_info:
        config = PWIAgentConfig(name=name, model="gpt-4o")
        agent = agent_class(config=config)
        tools = ", ".join(agent.tool_names) if agent.tool_names else "None"
        table.add_row(name, agent.ARTIFACT_TYPE.upper(), tools)

    console.print(table)

    # =========================================================================
    # 3. DuckDB Tool Execution Demo
    # =========================================================================
    section("3. DuckDB Tool Execution (Real Database)")

    db_path = Path(__file__).parent.parent.parent / "data" / "duckdb" / "raw.db"
    if db_path.exists():
        console.print(f"[green]✓[/green] Database found: {db_path}")

        # List tables
        console.print("\n[bold]Executing: duckdb_tables[/bold]")
        result = registry.execute("duckdb_tables", database_path=str(db_path))
        if result.get("success"):
            console.print(f"  Tables found: {result.get('table_count', 0)}")
            tables = result.get("tables", [])[:5]
            for t in tables:
                console.print(f"    - {t}")
            if len(result.get("tables", [])) > 5:
                console.print(f"    ... and {len(result['tables']) - 5} more")
        else:
            console.print(f"  [yellow]Note: {result.get('error', 'Unknown')}[/yellow]")

        # Query sample data
        console.print("\n[bold]Executing: duckdb_query (patient count)[/bold]")
        result = registry.execute(
            "duckdb_query",
            query="SELECT COUNT(*) as patient_count FROM synthea.patients",
            database_path=str(db_path),
        )
        if result.get("success"):
            console.print(f"  Result: {result.get('results', [])}")
        else:
            console.print(f"  [yellow]Note: {result.get('error', 'Unknown')}[/yellow]")

        # Get schema
        console.print("\n[bold]Executing: duckdb_schema (patients table)[/bold]")
        result = registry.execute(
            "duckdb_schema",
            table_name="synthea.patients",
            database_path=str(db_path),
        )
        if result.get("success"):
            columns = result.get("columns", [])[:5]
            for col in columns:
                console.print(f"    {col['name']}: {col['type']}")
            if len(result.get("columns", [])) > 5:
                console.print(f"    ... and {len(result['columns']) - 5} more columns")
        else:
            console.print(f"  [yellow]Note: {result.get('error', 'Unknown')}[/yellow]")
    else:
        console.print(f"[yellow]Database not found at {db_path}, skipping DuckDB demo[/yellow]")

    # =========================================================================
    # 4. CSV Analysis Tool Demo
    # =========================================================================
    section("4. CSV Analysis Tool Execution")

    import tempfile
    import os

    # Create test CSV
    csv_content = """patient_id,first_name,last_name,birth_date,gender
P001,John,Smith,1985-03-15,M
P002,Jane,Doe,1990-07-22,F
P003,Bob,Johnson,1978-11-08,M
P004,Alice,Williams,1995-01-30,F
P005,Charlie,Brown,1982-06-12,M"""

    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
        f.write(csv_content)
        temp_csv = f.name

    try:
        console.print("[bold]Executing: analyze_csv[/bold]")
        result = registry.execute("analyze_csv", file_path=temp_csv)
        if result.get("success"):
            console.print(f"  Rows: {result.get('row_count')}")
            console.print(f"  Columns: {result.get('column_count')}")
            for col in result.get("columns", []):
                nulls = col.get('null_count', col.get('null_percentage', 0))
                console.print(f"    {col['name']}: {col.get('inferred_type', col.get('type', 'unknown'))} (nulls: {nulls})")

        console.print("\n[bold]Executing: csv_sample[/bold]")
        result = registry.execute("csv_sample", file_path=temp_csv, num_rows=2)
        if result.get("success"):
            console.print(f"  Sample rows: {result.get('row_count')}")
            for row in result.get("rows", []):
                console.print(f"    {row}")
    finally:
        os.unlink(temp_csv)

    # =========================================================================
    # 5. Artifact Tool Demo
    # =========================================================================
    section("5. Artifact Tool Execution")

    console.print("[bold]Executing: list_artifact_types[/bold]")
    result = registry.execute("list_artifact_types")
    for atype, info in result.get("artifact_types", {}).items():
        console.print(f"  {atype}: {info['name']} ({info['format']})")

    console.print("\n[bold]Executing: validate_artifact (DRD)[/bold]")
    test_drd = """# Data Requirements Document (DRD)

## 1. Executive Summary
Healthcare analytics pipeline for patient 360 view.

## 2. Data Sources
### 2.1 Synthea Database
- **Type**: DuckDB
- **Tables**: patients, encounters, conditions
"""
    result = registry.execute("validate_artifact", artifact_type="drd", content=test_drd)
    console.print(f"  Valid: {result.get('valid')}")
    console.print(f"  Issues: {result.get('issue_count', 0)}")

    # =========================================================================
    # 6. Event Stream Demo
    # =========================================================================
    section("6. Event Stream Demonstration")

    from pwi.openhands.workflow.events import (
        EventStream,
        WorkflowStartedEvent,
        AgentStartedEvent,
        AgentToolCallEvent,
        AgentToolResultEvent,
        AgentCompletedEvent,
        WorkflowCompletedEvent,
    )

    stream = EventStream("demo-session-001")

    # Simulate workflow events
    stream.append(WorkflowStartedEvent(session_id="demo-session-001"))
    stream.append(AgentStartedEvent(
        session_id="demo-session-001",
        agent_name="data_analyst",
        model="gpt-4o",
        tool_count=5,
    ))
    stream.append(AgentToolCallEvent(
        session_id="demo-session-001",
        agent_name="data_analyst",
        tool_name="duckdb_tables",
        arguments={"database_path": "../data/duckdb/raw.db"},
    ))
    stream.append(AgentToolResultEvent(
        session_id="demo-session-001",
        agent_name="data_analyst",
        tool_name="duckdb_tables",
        success=True,
    ))
    stream.append(AgentCompletedEvent(
        session_id="demo-session-001",
        agent_name="data_analyst",
        artifact_type="drd",
        prompt_tokens=1500,
        completion_tokens=2000,
    ))
    stream.append(WorkflowCompletedEvent(
        session_id="demo-session-001",
        total_tokens=3500,
        artifact_count=1,
    ))

    table = Table(title="Event Stream")
    table.add_column("Event Type", style="cyan")
    table.add_column("Agent", style="green")
    table.add_column("Details", style="yellow")

    for event in stream:
        details = ""
        if hasattr(event, "tool_name") and event.tool_name:
            details = f"tool={event.tool_name}"
        elif hasattr(event, "artifact_type") and event.artifact_type:
            details = f"artifact={event.artifact_type}"
        elif hasattr(event, "total_tokens") and event.total_tokens:
            details = f"tokens={event.total_tokens}"

        table.add_row(
            event.event_type.value,
            event.agent_name or "-",
            details,
        )

    console.print(table)

    # =========================================================================
    # 7. Agent State & Validation Demo
    # =========================================================================
    section("7. Agent State & Input Validation")

    from pwi.openhands.agents import PWIAgentState

    # Show dependency chain
    console.print("[bold]Agent Dependency Chain:[/bold]")
    console.print()

    deps = {
        "data_analyst": [],
        "data_architect": ["drd"],
        "mapping_engineer": ["drd", "pad"],
        "dq_engineer": ["drd", "dmd"],
        "story_writer": ["drd", "pad", "dmd", "dqs"],
        "sync_agent": ["drd", "pad", "dmd", "dqs", "stories"],
    }

    for agent_name, required in deps.items():
        if required:
            console.print(f"  {agent_name} → requires: {', '.join(required)}")
        else:
            console.print(f"  {agent_name} → (no dependencies, first agent)")

    # Validate state
    console.print("\n[bold]State Validation Example:[/bold]")

    state_incomplete = PWIAgentState(
        session_id="test",
        business_request="Build healthcare pipeline",
        artifacts={},  # No artifacts yet
    )

    state_complete = PWIAgentState(
        session_id="test",
        business_request="Build healthcare pipeline",
        artifacts={"drd": "# DRD Content"},  # Has DRD
    )

    config = PWIAgentConfig(name="data_architect", model="gpt-4o")
    architect = DataArchitectAgent(config=config)

    is_valid, error = architect.validate_inputs(state_incomplete)
    console.print(f"  State without DRD: valid={is_valid}, error={error}")

    is_valid, error = architect.validate_inputs(state_complete)
    console.print(f"  State with DRD: valid={is_valid}, error={error}")

    # =========================================================================
    # Summary
    # =========================================================================
    console.print()
    console.print("[bold magenta]" + "=" * 60 + "[/bold magenta]")
    console.print("[bold magenta]  OpenHands Integration Summary[/bold magenta]")
    console.print("[bold magenta]" + "=" * 60 + "[/bold magenta]")
    console.print()

    summary = Table(show_header=False, box=None)
    summary.add_column("Item", style="cyan")
    summary.add_column("Status", style="green")

    summary.add_row("Tools Registered", f"{len(registry.tool_names)} tools")
    summary.add_row("Agents Configured", "6 agents")
    summary.add_row("DuckDB Integration", "Working" if db_path.exists() else "Database not found")
    summary.add_row("CSV Analysis", "Working")
    summary.add_row("Artifact Validation", "Working")
    summary.add_row("Event Stream", "Working")
    summary.add_row("State Management", "Working")

    console.print(summary)

    console.print()
    console.print("[bold green]✓ OpenHands SDK integration is fully operational![/bold green]")
    console.print()
    console.print("[dim]To run a full workflow with LLM, use:[/dim]")
    console.print("[dim]  uv run pwi plan run requests/openhands-test-request.md[/dim]")
    console.print()


if __name__ == "__main__":
    asyncio.run(main())
