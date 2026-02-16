"""Init command for Planning with Intent.

This module provides the `pwi init` command for initializing
a new PWI project.
"""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel

from pwi.config.loader import create_default_config

app = typer.Typer(help="Initialize a new PWI project")
console = Console()


@app.callback(invoke_without_command=True)
def init_project(
    project_type: str = typer.Option(
        "data_engineering",
        "--type",
        "-t",
        help="Project type (currently only data_engineering supported)",
    ),
    project_name: str = typer.Option(
        None,
        "--name",
        "-n",
        help="Project name (defaults to current directory name)",
    ),
    output_dir: Path = typer.Option(
        Path("."),
        "--dir",
        "-d",
        help="Directory to initialize project in",
    ),
    force: bool = typer.Option(
        False,
        "--force",
        "-f",
        help="Overwrite existing configuration",
    ),
) -> None:
    """Initialize a new PWI project.

    Creates the necessary directory structure and configuration files
    for running PWI workflows.
    """
    # Validate project type
    if project_type != "data_engineering":
        console.print(
            f"[red]Unsupported project type: {project_type}[/red]\n"
            "Currently only 'data_engineering' is supported."
        )
        raise typer.Exit(1)

    # Resolve project name
    if project_name is None:
        project_name = output_dir.resolve().name

    # Check for existing config
    config_path = output_dir / "pwi.yaml"
    if config_path.exists() and not force:
        console.print(
            f"[yellow]Configuration already exists at {config_path}[/yellow]\n"
            "Use --force to overwrite."
        )
        raise typer.Exit(1)

    console.print(
        Panel.fit(
            f"[bold blue]Initializing PWI Project[/bold blue]\n\n"
            f"[dim]Name:[/dim] {project_name}\n"
            f"[dim]Type:[/dim] {project_type}\n"
            f"[dim]Directory:[/dim] {output_dir.resolve()}",
            title="PWI Init",
        )
    )

    # Create directory structure
    directories = [
        output_dir / ".pwi" / "sessions",
        output_dir / ".pwi" / "logs",
        output_dir / "output",
        output_dir / "requests",
    ]

    for directory in directories:
        directory.mkdir(parents=True, exist_ok=True)
        console.print(f"  [green]✓[/green] Created {directory.relative_to(output_dir)}")

    # Create configuration file
    create_default_config(config_path)
    console.print("  [green]✓[/green] Created pwi.yaml")

    # Create example request file
    example_request = output_dir / "requests" / "example-request.md"
    if not example_request.exists():
        example_request.write_text(
            """# Example Data Engineering Request

## Business Context

We need to build a customer analytics pipeline that integrates data from
multiple sources to create a unified view of customer behavior.

## Data Sources

1. **Salesforce CRM**
   - Customer accounts and contacts
   - Opportunity and deal data
   - Activity history

2. **Web Analytics (Google Analytics)**
   - Page views and sessions
   - User journeys
   - Conversion events

3. **Transaction Database (PostgreSQL)**
   - Order history
   - Payment records
   - Product catalog

## Requirements

- Daily batch processing (data freshness: T+1)
- Support for historical backfill (last 2 years)
- Data quality checks for all critical fields
- SCD Type 2 for customer dimension

## Deliverables

- Customer 360 dimension table
- Daily activity fact table
- Customer segmentation model input

## SLA

- Pipeline completion by 6:00 AM UTC
- 99.5% uptime for analytics queries
""",
            encoding="utf-8",
        )
        console.print("  [green]✓[/green] Created requests/example-request.md")

    # Create .gitignore for PWI files
    gitignore_path = output_dir / ".pwi" / ".gitignore"
    if not gitignore_path.exists():
        gitignore_path.write_text(
            """# PWI local files
sessions/
logs/
*.log
""",
            encoding="utf-8",
        )
        console.print("  [green]✓[/green] Created .pwi/.gitignore")

    console.print(
        "\n[bold green]Project initialized successfully![/bold green]\n\n"
        "[dim]Next steps:[/dim]\n"
        "  1. Set environment variables (or create .env file):\n"
        "     export LLM_API_KEY=your-api-key\n"
        "     export LLM_BASE_URL=https://api.openai.com/v1\n"
        "     export LLM_MODEL=gpt-4o-mini\n"
        "  2. Edit pwi.yaml to customize settings\n"
        "  3. Create your request: requests/my-request.md\n"
        "  4. Run the workflow: pwi plan run requests/my-request.md\n"
    )
