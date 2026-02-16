"""File-based review handler for Planning with Intent.

This module provides file-based review functionality where artifacts
are saved to disk and the user can edit them before approval.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt

from pwi.review.base import BaseReviewHandler, ReviewResult

if TYPE_CHECKING:
    from pwi.workflow.session import Session, SessionArtifact

console = Console()


class FileReviewHandler(BaseReviewHandler):
    """File-based review handler.

    Saves artifacts to disk for review and editing.
    """

    def __init__(
        self,
        review_dir: Path | None = None,
        timeout_minutes: int = 60,
    ) -> None:
        """Initialize file review handler.

        Args:
            review_dir: Directory for review files (defaults to .pwi/review/).
            timeout_minutes: Maximum wait time for review in minutes.
        """
        self.review_dir = review_dir or Path(".pwi/review")
        self.timeout_minutes = timeout_minutes

    async def review(
        self,
        session: Session,
        agent_name: str,
        artifact: SessionArtifact,
    ) -> ReviewResult:
        """Perform a file-based review.

        Args:
            session: Current workflow session.
            agent_name: Name of the agent that produced the artifact.
            artifact: The artifact to review.

        Returns:
            ReviewResult with the review decision.
        """
        # Create review directory
        review_path = self.review_dir / session.session_id
        review_path.mkdir(parents=True, exist_ok=True)

        # Determine file extension
        ext_map = {
            "markdown": ".md",
            "csv": ".csv",
            "yaml": ".yaml",
            "json": ".json",
        }
        ext = ext_map.get(artifact.format, ".txt")

        # Write artifact to file
        artifact_file = review_path / f"{artifact.type}{ext}"
        artifact_file.write_text(artifact.content, encoding="utf-8")

        # Create approval marker file path
        approval_file = review_path / f"{artifact.type}.approved"
        rejection_file = review_path / f"{artifact.type}.rejected"

        # Clean up any existing marker files
        if approval_file.exists():
            approval_file.unlink()
        if rejection_file.exists():
            rejection_file.unlink()

        # Display instructions
        console.print()
        console.print(
            Panel.fit(
                f"[bold blue]File Review: {agent_name.replace('_', ' ').title()}[/bold blue]\n\n"
                f"[dim]Artifact saved to:[/dim]\n"
                f"  {artifact_file.absolute()}\n\n"
                "[bold]Review Options:[/bold]\n"
                f"  1. Edit the file as needed\n"
                f"  2. Create '{artifact.type}.approved' to approve\n"
                f"     OR '{artifact.type}.rejected' to reject\n\n"
                "[dim]Or respond to the prompt below[/dim]",
                title="📁 File Review",
            )
        )

        # Prompt for action (with polling for file markers)
        console.print()
        console.print(
            f"[dim]Waiting for review... (timeout: {self.timeout_minutes} minutes)[/dim]"
        )
        console.print(
            "[dim]Press Enter when done reviewing, or type 'approve'/'reject'[/dim]"
        )

        # Wait for user input or file marker
        result = await self._wait_for_review(
            artifact_file=artifact_file,
            approval_file=approval_file,
            rejection_file=rejection_file,
            original_content=artifact.content,
        )

        # Clean up marker files
        if approval_file.exists():
            approval_file.unlink()
        if rejection_file.exists():
            rejection_file.unlink()

        return result

    async def _wait_for_review(
        self,
        artifact_file: Path,
        approval_file: Path,
        rejection_file: Path,
        original_content: str,
    ) -> ReviewResult:
        """Wait for review completion via file markers or user input.

        Args:
            artifact_file: Path to the artifact file.
            approval_file: Path to approval marker file.
            rejection_file: Path to rejection marker file.
            original_content: Original artifact content.

        Returns:
            ReviewResult based on user action.
        """
        # Simple approach: prompt user
        action = Prompt.ask(
            "Action",
            choices=["approve", "reject", "a", "r"],
            default="approve",
        )

        # Read potentially edited content
        edited_content = artifact_file.read_text(encoding="utf-8")
        content_changed = edited_content != original_content

        if action.lower() in ("approve", "a"):
            feedback = None
            if content_changed:
                feedback = "Approved with edits"
                console.print("[green]✓ Approved with edits[/green]")
            else:
                console.print("[green]✓ Approved[/green]")

            return ReviewResult(
                approved=True,
                feedback=feedback,
                edited_content=edited_content if content_changed else None,
            )
        else:
            feedback = Prompt.ask(
                "Rejection reason",
                default="Rejected by reviewer",
            )
            console.print("[red]✗ Rejected[/red]")
            return ReviewResult(
                approved=False,
                feedback=feedback,
            )
