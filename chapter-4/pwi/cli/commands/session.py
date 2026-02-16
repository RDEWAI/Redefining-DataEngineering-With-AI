"""Session management commands for Planning with Intent.

This module provides commands for listing, resuming, and managing
workflow sessions.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import typer
from rich.console import Console
from rich.table import Table

from pwi.config.loader import load_config
from pwi.workflow.session import Session, SessionManager
from pwi.workflow.states import WorkflowState

if TYPE_CHECKING:
    from pwi.config.schema import PWIConfig

app = typer.Typer(help="Manage workflow sessions")
console = Console()


@app.command("list")
def list_sessions(
    limit: int = typer.Option(10, "--limit", "-n", help="Maximum sessions to show"),
    all_sessions: bool = typer.Option(False, "--all", "-a", help="Show all sessions"),
    state: str = typer.Option(None, "--state", "-s", help="Filter by state"),
) -> None:
    """List workflow sessions."""
    config = load_config()
    session_manager = SessionManager(config.project.session_dir)

    sessions = session_manager.list_sessions()

    # Filter by state if specified
    if state:
        sessions = [s for s in sessions if s.current_state == state]

    # Apply limit
    if not all_sessions:
        sessions = sessions[:limit]

    if not sessions:
        console.print("[yellow]No sessions found.[/yellow]")
        return

    # Create table
    table = Table(title="PWI Sessions", show_header=True)
    table.add_column("ID", style="cyan")
    table.add_column("Project", style="green")
    table.add_column("State", style="yellow")
    table.add_column("Created", style="dim")
    table.add_column("Artifacts")
    table.add_column("Tokens", justify="right")
    table.add_column("Cost", justify="right")

    for session in sessions:
        state_obj = session.get_state()
        state_color = {
            WorkflowState.COMPLETED: "green",
            WorkflowState.FAILED: "red",
            WorkflowState.CANCELLED: "yellow",
            WorkflowState.PAUSED: "yellow",
        }.get(state_obj, "blue")

        table.add_row(
            session.session_id,
            session.project_name or "-",
            f"[{state_color}]{session.current_state}[/{state_color}]",
            session.created_at.strftime("%Y-%m-%d %H:%M"),
            str(len(session.artifacts)),
            f"{session.get_total_tokens():,}",
            session.get_formatted_cost(),
        )

    console.print(table)
    console.print(f"\n[dim]Showing {len(sessions)} session(s)[/dim]")


@app.command("status")
def session_status(
    session_id: str = typer.Argument(..., help="Session ID to check"),
) -> None:
    """Show detailed status of a session."""
    config = load_config()
    session_manager = SessionManager(config.project.session_dir)

    if not session_manager.exists(session_id):
        console.print(f"[red]Session not found: {session_id}[/red]")
        raise typer.Exit(1)

    session = session_manager.load(session_id)

    # Build detailed status
    console.print(f"\n[bold]Session: {session_id}[/bold]\n")
    console.print(f"  [dim]Project:[/dim] {session.project_name}")
    console.print(f"  [dim]State:[/dim] {session.current_state}")
    console.print(f"  [dim]Created:[/dim] {session.created_at}")
    console.print(f"  [dim]Updated:[/dim] {session.updated_at}")

    if session.request_path:
        console.print(f"  [dim]Request:[/dim] {session.request_path}")

    console.print(f"\n[bold]Artifacts ({len(session.artifacts)})[/bold]")
    if session.artifacts:
        for artifact_type, artifact in session.artifacts.items():
            console.print(
                f"  • {artifact_type.upper()} v{artifact.version} "
                f"[dim](from {artifact.agent})[/dim]"
            )
    else:
        console.print("  [dim]No artifacts yet[/dim]")

    console.print(f"\n[bold]Reviews ({len(session.reviews)})[/bold]")
    if session.reviews:
        for review in session.reviews:
            status = "[green]✓[/green]" if review.approved else "[red]✗[/red]"
            console.print(f"  {status} {review.agent} - {review.reviewed_at}")
    else:
        console.print("  [dim]No reviews yet[/dim]")

    console.print("\n[bold]Token Usage & Cost[/bold]")
    console.print(f"  Total: {session.get_total_tokens():,} tokens")
    console.print(f"  Cost: {session.get_formatted_cost()}")
    if session.token_usage:
        for usage in session.token_usage:
            cost_str = f"${usage.cost_usd}" if usage.cost_usd else ""
            console.print(
                f"  • {usage.agent}: {usage.total_tokens:,} tokens {cost_str} "
                f"[dim]({usage.model})[/dim]"
            )

    if session.error_message:
        console.print(f"\n[red]Error: {session.error_message}[/red]")


@app.command("resume")
def resume_session(
    session_id: str = typer.Argument(..., help="Session ID to resume"),
    auto_approve: bool = typer.Option(
        False,
        "--auto-approve",
        "-y",
        help="Automatically approve all review gates",
    ),
    skip_review: bool = typer.Option(
        False,
        "--skip-review",
        help="Skip all review gates",
    ),
) -> None:
    """Resume a paused workflow session."""
    import asyncio

    from rich.panel import Panel

    from pwi.workflow.states import get_resume_agent

    config = load_config()
    session_manager = SessionManager(config.project.session_dir)

    if not session_manager.exists(session_id):
        console.print(f"[red]Session not found: {session_id}[/red]")
        raise typer.Exit(1)

    session = session_manager.load(session_id)

    if session.is_terminal():
        console.print(
            f"[yellow]Session is in terminal state: {session.current_state}[/yellow]\n"
            "Cannot resume a completed, failed, or cancelled session."
        )
        raise typer.Exit(1)

    # Determine which agent to resume from
    resume_from = get_resume_agent(session.artifacts)

    if resume_from is None:
        console.print("[green]Session has completed all agents.[/green]")
        raise typer.Exit(0)

    # Check for API key and base URL
    if not config.llm.api_key:
        console.print(
            "[red]No API key configured![/red]\n"
            "Set LLM_API_KEY environment variable or update pwi.yaml"
        )
        raise typer.Exit(1)

    if not config.llm.base_url:
        console.print(
            "[red]No LLM base URL configured![/red]\n"
            "Set LLM_BASE_URL environment variable or update pwi.yaml"
        )
        raise typer.Exit(1)

    console.print(
        Panel.fit(
            f"[bold blue]Resuming PWI Workflow[/bold blue]\n\n"
            f"[dim]Session ID:[/dim] {session.session_id}\n"
            f"[dim]Completed Artifacts:[/dim] {len(session.artifacts)}\n"
            f"[dim]Resume From:[/dim] {resume_from.replace('_', ' ').title()}",
            title="PWI Resume",
        )
    )

    # Run the workflow from the resume point
    try:
        asyncio.run(
            _resume_workflow(
                session=session,
                session_manager=session_manager,
                config=config,
                resume_from=resume_from,
                auto_approve=auto_approve,
                skip_review=skip_review,
            )
        )
    except KeyboardInterrupt:
        console.print("\n[yellow]Workflow interrupted. Session saved.[/yellow]")
        session.set_state(WorkflowState.PAUSED)
        session_manager.save(session)
        console.print(f"Resume with: pwi session resume {session.session_id}")
        raise typer.Exit(0)
    except Exception as e:
        console.print(f"\n[red]Workflow failed: {e}[/red]")
        session.set_state(WorkflowState.FAILED)
        session.error_message = str(e)
        session_manager.save(session)
        raise typer.Exit(1)

    # Show completion summary
    if session.is_complete():
        console.print(
            Panel.fit(
                f"[bold green]Workflow Complete![/bold green]\n\n"
                f"[dim]Session:[/dim] {session.session_id}\n"
                f"[dim]Artifacts:[/dim] {len(session.artifacts)}\n"
                f"[dim]Total Tokens:[/dim] {session.get_total_tokens():,}\n"
                f"[dim]Estimated Cost:[/dim] {session.get_formatted_cost()}\n"
                f"[dim]Output:[/dim] {config.project.output_dir}",
                title="Success",
            )
        )


async def _resume_workflow(
    session: Session,
    session_manager: SessionManager,
    config: PWIConfig,
    resume_from: str,
    auto_approve: bool,
    skip_review: bool,
) -> None:
    """Resume a workflow from a specific agent."""
    from pwi.llm.client import LLMClient
    from pwi.workflow.orchestrator import WorkflowOrchestrator

    # Initialize LLM client
    llm_client = LLMClient(
        api_key=config.llm.api_key,
        base_url=config.llm.base_url,
        default_model=config.llm.default_model,
    )

    try:
        # Initialize orchestrator
        orchestrator = WorkflowOrchestrator(
            session=session,
            session_manager=session_manager,
            config=config,
            llm_client=llm_client,
            auto_approve=auto_approve,
            skip_review=skip_review,
        )

        # Run from resume point
        success = await orchestrator.run(resume_from=resume_from)

        if not success:
            console.print("\n[yellow]Workflow did not complete successfully.[/yellow]")
            console.print(
                f"Run 'pwi session status {session.session_id}' to check session state."
            )

    finally:
        # Always close LLM client
        await llm_client.aclose()


@app.command("delete")
def delete_session(
    session_id: str = typer.Argument(..., help="Session ID to delete"),
    force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation"),
) -> None:
    """Delete a workflow session."""
    config = load_config()
    session_manager = SessionManager(config.project.session_dir)

    if not session_manager.exists(session_id):
        console.print(f"[red]Session not found: {session_id}[/red]")
        raise typer.Exit(1)

    session = session_manager.load(session_id)

    if not force:
        confirm = typer.confirm(
            f"Delete session {session_id} ({session.current_state})?"
        )
        if not confirm:
            console.print("[yellow]Cancelled[/yellow]")
            raise typer.Exit(0)

    session_manager.delete(session_id)
    console.print(f"[green]Session {session_id} deleted.[/green]")


@app.command("export")
def export_session(
    session_id: str = typer.Argument(..., help="Session ID to export"),
    output_dir: str = typer.Option(
        None,
        "--output",
        "-o",
        help="Output directory (defaults to current directory)",
    ),
) -> None:
    """Export session artifacts to files."""
    from pathlib import Path

    config = load_config()
    session_manager = SessionManager(config.project.session_dir)

    if not session_manager.exists(session_id):
        console.print(f"[red]Session not found: {session_id}[/red]")
        raise typer.Exit(1)

    session = session_manager.load(session_id)

    if not session.artifacts:
        console.print("[yellow]No artifacts to export.[/yellow]")
        raise typer.Exit(0)

    # Determine output directory
    out_path = Path(output_dir) if output_dir else Path.cwd() / session_id
    out_path.mkdir(parents=True, exist_ok=True)

    # Export each artifact
    for artifact_type, artifact in session.artifacts.items():
        # Determine file extension
        ext_map = {
            "markdown": ".md",
            "csv": ".csv",
            "yaml": ".yaml",
            "json": ".json",
        }
        ext = ext_map.get(artifact.format, ".txt")

        filename = f"{artifact_type}{ext}"
        filepath = out_path / filename

        filepath.write_text(artifact.content, encoding="utf-8")
        console.print(f"  [green]✓[/green] Exported {filename}")

    console.print(f"\n[green]Artifacts exported to {out_path}[/green]")
