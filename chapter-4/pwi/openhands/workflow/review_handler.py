"""Review handler for OpenHands-based PWI workflow.

This module provides review gate functionality that integrates
with the EventStream for pausing and resuming workflows.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich.syntax import Syntax

from pwi.openhands.workflow.events import (
    EventStream,
    ReviewApprovedEvent,
    ReviewPendingEvent,
    ReviewRejectedEvent,
    ReviewTimeoutEvent,
    WorkflowPausedEvent,
)
from pwi.utils.logging import get_logger

if TYPE_CHECKING:
    from pwi.workflow.session import Artifact, Session

logger = get_logger("openhands.workflow.review_handler")
console = Console()


@dataclass
class ReviewResult:
    """Result of a review gate."""

    approved: bool
    feedback: str = ""
    edited_content: str | None = None
    was_edited: bool = False


class BaseReviewHandler(ABC):
    """Abstract base class for review handlers.

    Review handlers manage the review gate logic, which can be:
    - CLI-based: Interactive prompts in terminal
    - File-based: Write to file, wait for edits
    - Dashboard-based: Web UI for review
    """

    def __init__(self, event_stream: EventStream | None = None) -> None:
        """Initialize the review handler.

        Args:
            event_stream: Optional event stream to emit events to.
        """
        self.event_stream = event_stream

    @abstractmethod
    async def review(
        self,
        session: Session,
        agent_name: str,
        artifact: Artifact,
    ) -> ReviewResult:
        """Perform review of an agent's output.

        Args:
            session: Current workflow session.
            agent_name: Name of the agent being reviewed.
            artifact: Artifact to review.

        Returns:
            ReviewResult with approval status and optional feedback.
        """
        pass

    def _emit_pending(self, session_id: str, agent_name: str, artifact_type: str) -> None:
        """Emit review pending event."""
        if self.event_stream:
            event = ReviewPendingEvent(
                session_id=session_id,
                agent_name=agent_name,
                artifact_type=artifact_type,
            )
            self.event_stream.append(event)

    def _emit_approved(
        self,
        session_id: str,
        agent_name: str,
        feedback: str,
        was_edited: bool,
    ) -> None:
        """Emit review approved event."""
        if self.event_stream:
            event = ReviewApprovedEvent(
                session_id=session_id,
                agent_name=agent_name,
                feedback=feedback,
                was_edited=was_edited,
            )
            self.event_stream.append(event)

    def _emit_rejected(
        self,
        session_id: str,
        agent_name: str,
        feedback: str,
        reason: str,
    ) -> None:
        """Emit review rejected event."""
        if self.event_stream:
            event = ReviewRejectedEvent(
                session_id=session_id,
                agent_name=agent_name,
                feedback=feedback,
                rejection_reason=reason,
            )
            self.event_stream.append(event)


class CLIReviewHandler(BaseReviewHandler):
    """CLI-based review handler using Rich for interactive prompts."""

    def __init__(
        self,
        event_stream: EventStream | None = None,
        show_full_content: bool = False,
        max_preview_lines: int = 30,
    ) -> None:
        """Initialize CLI review handler.

        Args:
            event_stream: Optional event stream.
            show_full_content: Whether to show full artifact content.
            max_preview_lines: Maximum lines to show in preview.
        """
        super().__init__(event_stream)
        self.show_full_content = show_full_content
        self.max_preview_lines = max_preview_lines

    async def review(
        self,
        session: Session,
        agent_name: str,
        artifact: Artifact,
    ) -> ReviewResult:
        """Perform CLI-based review.

        Args:
            session: Current workflow session.
            agent_name: Name of the agent being reviewed.
            artifact: Artifact to review.

        Returns:
            ReviewResult with approval status.
        """
        self._emit_pending(session.session_id, agent_name, artifact.artifact_type)

        # Display artifact info
        console.print()
        console.print(
            Panel(
                f"[bold blue]Review Gate: {agent_name.replace('_', ' ').title()}[/bold blue]\n"
                f"Artifact: {artifact.artifact_type.upper()} ({artifact.format})\n"
                f"Size: {len(artifact.content)} characters",
                title="📋 Review Required",
            )
        )

        # Show preview or full content
        content_lines = artifact.content.split("\n")
        if self.show_full_content or len(content_lines) <= self.max_preview_lines:
            display_content = artifact.content
        else:
            display_content = "\n".join(content_lines[: self.max_preview_lines])
            display_content += f"\n\n... ({len(content_lines) - self.max_preview_lines} more lines)"

        # Choose syntax highlighting based on format
        lexer = {
            "markdown": "markdown",
            "csv": "text",
            "yaml": "yaml",
        }.get(artifact.format, "text")

        console.print(
            Syntax(display_content, lexer, theme="monokai", line_numbers=True)
        )

        # Ask for approval
        console.print()
        approved = Confirm.ask("[bold]Approve this artifact?[/bold]", default=True)

        feedback = ""
        if not approved:
            feedback = Prompt.ask(
                "[yellow]Please provide feedback for rejection[/yellow]",
                default="",
            )
            self._emit_rejected(
                session.session_id, agent_name, feedback, "user_rejected"
            )
        else:
            # Optional feedback even when approved
            if Confirm.ask("Would you like to add feedback?", default=False):
                feedback = Prompt.ask("[dim]Feedback (optional)[/dim]", default="")
            self._emit_approved(session.session_id, agent_name, feedback, False)

        return ReviewResult(approved=approved, feedback=feedback)


class FileReviewHandler(BaseReviewHandler):
    """File-based review handler that writes artifacts to files for editing."""

    def __init__(
        self,
        event_stream: EventStream | None = None,
        review_dir: Path | None = None,
        timeout_minutes: int = 30,
    ) -> None:
        """Initialize file review handler.

        Args:
            event_stream: Optional event stream.
            review_dir: Directory to write review files.
            timeout_minutes: Timeout for file-based review.
        """
        super().__init__(event_stream)
        self.review_dir = review_dir or Path("output/review")
        self.timeout_minutes = timeout_minutes

    async def review(
        self,
        session: Session,
        agent_name: str,
        artifact: Artifact,
    ) -> ReviewResult:
        """Perform file-based review.

        Args:
            session: Current workflow session.
            agent_name: Name of the agent being reviewed.
            artifact: Artifact to review.

        Returns:
            ReviewResult with approval status and optional edits.
        """
        import asyncio

        self._emit_pending(session.session_id, agent_name, artifact.artifact_type)

        # Create review directory
        session_review_dir = self.review_dir / session.session_id
        session_review_dir.mkdir(parents=True, exist_ok=True)

        # Write artifact to file
        ext_map = {"markdown": "md", "csv": "csv", "yaml": "yaml"}
        ext = ext_map.get(artifact.format, "txt")
        review_file = session_review_dir / f"{artifact.artifact_type}.{ext}"
        review_file.write_text(artifact.content, encoding="utf-8")

        # Write instructions
        instructions_file = session_review_dir / "REVIEW_INSTRUCTIONS.md"
        instructions = f"""# Review Instructions

## Artifact: {artifact.artifact_type.upper()}
## Agent: {agent_name}

### How to Review:
1. Open the file: `{review_file.name}`
2. Review the content
3. Make any necessary edits directly in the file
4. Create one of the following files to signal your decision:
   - `APPROVED` - Approve with current content (or edits)
   - `REJECTED` - Reject with reason in file content

### Timeout:
This review will timeout after {self.timeout_minutes} minutes.

### Session Info:
- Session ID: {session.session_id}
- Review started: {artifact.created_at}
"""
        instructions_file.write_text(instructions, encoding="utf-8")

        console.print(
            Panel(
                f"[bold]File-based review for {agent_name}[/bold]\n\n"
                f"Review file: [cyan]{review_file}[/cyan]\n"
                f"Instructions: [cyan]{instructions_file}[/cyan]\n\n"
                f"Create 'APPROVED' or 'REJECTED' file to continue.\n"
                f"Timeout: {self.timeout_minutes} minutes",
                title="📁 File Review",
            )
        )

        # Wait for response file
        approved_file = session_review_dir / "APPROVED"
        rejected_file = session_review_dir / "REJECTED"

        timeout_seconds = self.timeout_minutes * 60
        check_interval = 5  # seconds
        elapsed = 0

        while elapsed < timeout_seconds:
            if approved_file.exists():
                # Read possibly edited content
                edited_content = review_file.read_text(encoding="utf-8")
                was_edited = edited_content != artifact.content
                feedback = approved_file.read_text(encoding="utf-8").strip()

                # Cleanup
                approved_file.unlink()
                self._emit_approved(
                    session.session_id, agent_name, feedback, was_edited
                )

                return ReviewResult(
                    approved=True,
                    feedback=feedback,
                    edited_content=edited_content if was_edited else None,
                    was_edited=was_edited,
                )

            if rejected_file.exists():
                feedback = rejected_file.read_text(encoding="utf-8").strip()

                # Cleanup
                rejected_file.unlink()
                self._emit_rejected(
                    session.session_id, agent_name, feedback, "user_rejected"
                )

                return ReviewResult(approved=False, feedback=feedback)

            await asyncio.sleep(check_interval)
            elapsed += check_interval

        # Timeout
        if self.event_stream:
            event = ReviewTimeoutEvent(
                session_id=session.session_id,
                agent_name=agent_name,
                timeout_minutes=self.timeout_minutes,
            )
            self.event_stream.append(event)

        return ReviewResult(
            approved=False,
            feedback=f"Review timed out after {self.timeout_minutes} minutes",
        )


class AutoApproveHandler(BaseReviewHandler):
    """Handler that auto-approves all reviews."""

    async def review(
        self,
        session: Session,
        agent_name: str,
        artifact: Artifact,
    ) -> ReviewResult:
        """Auto-approve review.

        Args:
            session: Current workflow session.
            agent_name: Name of the agent being reviewed.
            artifact: Artifact to review.

        Returns:
            Always approved ReviewResult.
        """
        self._emit_approved(
            session.session_id, agent_name, "Auto-approved", False
        )
        return ReviewResult(approved=True, feedback="Auto-approved")


class SkipReviewHandler(BaseReviewHandler):
    """Handler that skips reviews entirely."""

    async def review(
        self,
        session: Session,
        agent_name: str,
        artifact: Artifact,
    ) -> ReviewResult:
        """Skip review.

        Args:
            session: Current workflow session.
            agent_name: Name of the agent being reviewed.
            artifact: Artifact to review.

        Returns:
            Approved ReviewResult without events.
        """
        return ReviewResult(approved=True)


def get_review_handler(
    mode: str,
    event_stream: EventStream | None = None,
    **kwargs: Any,
) -> BaseReviewHandler:
    """Factory function to create a review handler.

    Args:
        mode: Review mode ('cli', 'file', 'auto', 'skip').
        event_stream: Optional event stream.
        **kwargs: Additional handler-specific arguments.

    Returns:
        Configured review handler.
    """
    handlers = {
        "cli": lambda: CLIReviewHandler(event_stream=event_stream, **kwargs),
        "file": lambda: FileReviewHandler(event_stream=event_stream, **kwargs),
        "auto": lambda: AutoApproveHandler(event_stream=event_stream),
        "skip": lambda: SkipReviewHandler(event_stream=event_stream),
    }

    factory = handlers.get(mode)
    if not factory:
        raise ValueError(f"Unknown review mode: {mode}. Valid modes: {list(handlers.keys())}")

    return factory()
