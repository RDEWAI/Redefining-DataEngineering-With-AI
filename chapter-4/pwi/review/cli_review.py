"""CLI-based review handler for Planning with Intent.

This module provides interactive CLI review functionality.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.prompt import Prompt

from pwi.review.base import BaseReviewHandler, ReviewResult

if TYPE_CHECKING:
    from pwi.workflow.session import Session, SessionArtifact

console = Console()


class CLIReviewHandler(BaseReviewHandler):
    """Interactive CLI review handler.

    Displays the artifact and prompts the user for approval.
    """

    def __init__(self, show_full_content: bool = False) -> None:
        """Initialize CLI review handler.

        Args:
            show_full_content: Whether to show full artifact content.
        """
        self.show_full_content = show_full_content

    async def review(
        self,
        session: Session,
        agent_name: str,
        artifact: SessionArtifact,
    ) -> ReviewResult:
        """Perform an interactive CLI review.

        Args:
            session: Current workflow session.
            agent_name: Name of the agent that produced the artifact.
            artifact: The artifact to review.

        Returns:
            ReviewResult with the review decision.
        """
        # Display header
        console.print()
        console.print(
            Panel.fit(
                f"[bold blue]Review Gate: {agent_name.replace('_', ' ').title()}[/bold blue]\n\n"
                f"[dim]Session:[/dim] {session.session_id}\n"
                f"[dim]Artifact:[/dim] {artifact.type.upper()}\n"
                f"[dim]Format:[/dim] {artifact.format}\n"
                f"[dim]Length:[/dim] {len(artifact.content):,} characters",
                title="📋 Artifact Review",
            )
        )

        # Display content preview or full content
        console.print("\n[bold]Artifact Preview:[/bold]\n")
        if self.show_full_content:
            self._display_artifact(artifact)
        else:
            self._display_preview(artifact, max_lines=30)

        # Prompt for action
        console.print()
        action = Prompt.ask(
            "Action",
            choices=["approve", "reject", "view", "a", "r", "v"],
            default="approve",
        )

        # Handle view action
        while action.lower() in ("view", "v"):
            self._display_artifact(artifact)
            action = Prompt.ask(
                "Action",
                choices=["approve", "reject", "a", "r"],
                default="approve",
            )

        # Handle approve/reject
        if action.lower() in ("approve", "a"):
            feedback = Prompt.ask(
                "Feedback (optional)",
                default="",
            )
            console.print("[green]✓ Approved[/green]")
            return ReviewResult(
                approved=True,
                feedback=feedback if feedback else None,
            )
        else:
            feedback = Prompt.ask(
                "Rejection reason",
                default="",
            )
            if not feedback:
                feedback = "Rejected without specific feedback"
            console.print("[red]✗ Rejected[/red]")
            return ReviewResult(
                approved=False,
                feedback=feedback,
            )

    def _display_artifact(self, artifact: SessionArtifact) -> None:
        """Display full artifact content."""
        if artifact.format == "markdown":
            console.print(Markdown(artifact.content))
        else:
            console.print(artifact.content)

    def _display_preview(
        self,
        artifact: SessionArtifact,
        max_lines: int = 30,
    ) -> None:
        """Display a preview of the artifact content."""
        lines = artifact.content.split("\n")
        preview_lines = lines[:max_lines]
        preview = "\n".join(preview_lines)

        if len(lines) > max_lines:
            preview += f"\n\n[dim]... ({len(lines) - max_lines} more lines)[/dim]"
            preview += "\n[dim]Enter 'v' or 'view' to see full content[/dim]"

        if artifact.format == "markdown":
            console.print(Markdown(preview))
        else:
            console.print(preview)
