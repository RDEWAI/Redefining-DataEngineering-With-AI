"""Review commands for Planning with Intent.

This module provides commands for reviewing and approving
artifacts at review gates.
"""

from __future__ import annotations

import typer
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel

from pwi.config.loader import load_config
from pwi.workflow.session import SessionManager
from pwi.workflow.states import WorkflowState

app = typer.Typer(help="Review and approve artifacts")
console = Console()


@app.command("show")
def show_review(
    session_id: str = typer.Argument(..., help="Session ID to review"),
) -> None:
    """Show the current artifact pending review."""
    config = load_config()
    session_manager = SessionManager(config.project.session_dir)

    if not session_manager.exists(session_id):
        console.print(f"[red]Session not found: {session_id}[/red]")
        raise typer.Exit(1)

    session = session_manager.load(session_id)
    state = session.get_state()

    # Check if in review state
    if not WorkflowState.is_review(state):
        console.print(
            f"[yellow]Session is not in a review state: {state.value}[/yellow]"
        )
        raise typer.Exit(1)

    # Get the agent that's pending review
    agent_name = WorkflowState.get_agent_name(state)
    if not agent_name:
        console.print("[red]Could not determine agent for review[/red]")
        raise typer.Exit(1)

    # Map agent to artifact type
    artifact_map = {
        "data_analyst": "drd",
        "data_architect": "pad",
        "mapping_engineer": "dmd",
        "dq_engineer": "dqs",
        "story_writer": "stories",
    }
    artifact_type = artifact_map.get(agent_name)

    if not artifact_type or artifact_type not in session.artifacts:
        console.print(f"[red]Artifact not found for {agent_name}[/red]")
        raise typer.Exit(1)

    artifact = session.artifacts[artifact_type]

    # Display the artifact
    console.print(
        Panel.fit(
            f"[bold]Review Required[/bold]\n\n"
            f"[dim]Session:[/dim] {session_id}\n"
            f"[dim]Agent:[/dim] {agent_name}\n"
            f"[dim]Artifact:[/dim] {artifact_type.upper()}\n"
            f"[dim]Version:[/dim] {artifact.version}",
            title="Pending Review",
        )
    )

    console.print("\n[bold]Artifact Content:[/bold]\n")

    # Render based on format
    if artifact.format == "markdown":
        console.print(Markdown(artifact.content))
    else:
        console.print(artifact.content)

    console.print(
        "\n[dim]Use 'pwi review approve' or 'pwi review reject' to continue.[/dim]"
    )


@app.command("approve")
def approve_review(
    session_id: str = typer.Argument(..., help="Session ID to approve"),
    comment: str = typer.Option(
        None,
        "--comment",
        "-c",
        help="Optional comment/feedback",
    ),
) -> None:
    """Approve the current artifact and continue workflow."""
    config = load_config()
    session_manager = SessionManager(config.project.session_dir)

    if not session_manager.exists(session_id):
        console.print(f"[red]Session not found: {session_id}[/red]")
        raise typer.Exit(1)

    session = session_manager.load(session_id)
    state = session.get_state()

    # Check if in review state
    if not WorkflowState.is_review(state):
        console.print(
            f"[yellow]Session is not in a review state: {state.value}[/yellow]"
        )
        raise typer.Exit(1)

    agent_name = WorkflowState.get_agent_name(state)

    # Record the approval
    session.add_review(
        agent=agent_name or "unknown",
        approved=True,
        feedback=comment,
    )
    session_manager.save(session)

    console.print(
        f"[green]✓ Approved {agent_name} artifact[/green]"
    )
    if comment:
        console.print(f"[dim]Comment: {comment}[/dim]")

    console.print(
        "\n[yellow]Note: Automatic workflow continuation coming in Phase 2.[/yellow]\n"
        f"Run 'pwi session resume {session_id}' to continue."
    )


@app.command("reject")
def reject_review(
    session_id: str = typer.Argument(..., help="Session ID to reject"),
    reason: str = typer.Option(
        ...,
        "--reason",
        "-r",
        help="Reason for rejection (required)",
    ),
) -> None:
    """Reject the current artifact and request regeneration."""
    config = load_config()
    session_manager = SessionManager(config.project.session_dir)

    if not session_manager.exists(session_id):
        console.print(f"[red]Session not found: {session_id}[/red]")
        raise typer.Exit(1)

    session = session_manager.load(session_id)
    state = session.get_state()

    # Check if in review state
    if not WorkflowState.is_review(state):
        console.print(
            f"[yellow]Session is not in a review state: {state.value}[/yellow]"
        )
        raise typer.Exit(1)

    agent_name = WorkflowState.get_agent_name(state)

    # Record the rejection
    session.add_review(
        agent=agent_name or "unknown",
        approved=False,
        feedback=reason,
    )
    session_manager.save(session)

    console.print(
        f"[yellow]✗ Rejected {agent_name} artifact[/yellow]"
    )
    console.print(f"[dim]Reason: {reason}[/dim]")

    console.print(
        "\n[yellow]Note: Automatic regeneration coming in Phase 2.[/yellow]\n"
        f"Run 'pwi session resume {session_id}' to regenerate."
    )


@app.command("history")
def review_history(
    session_id: str = typer.Argument(..., help="Session ID to show history for"),
) -> None:
    """Show review history for a session."""
    from rich.table import Table

    config = load_config()
    session_manager = SessionManager(config.project.session_dir)

    if not session_manager.exists(session_id):
        console.print(f"[red]Session not found: {session_id}[/red]")
        raise typer.Exit(1)

    session = session_manager.load(session_id)

    if not session.reviews:
        console.print("[yellow]No review history for this session.[/yellow]")
        return

    table = Table(title=f"Review History - {session_id}", show_header=True)
    table.add_column("Agent", style="cyan")
    table.add_column("Decision", style="green")
    table.add_column("Timestamp", style="dim")
    table.add_column("Feedback")

    for review in session.reviews:
        decision = "[green]Approved[/green]" if review.approved else "[red]Rejected[/red]"
        table.add_row(
            review.agent,
            decision,
            review.reviewed_at.strftime("%Y-%m-%d %H:%M:%S"),
            review.feedback or "-",
        )

    console.print(table)
