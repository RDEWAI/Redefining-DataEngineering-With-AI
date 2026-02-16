"""Base review handler for Planning with Intent.

This module defines the abstract base class for review handlers.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pwi.workflow.session import Session, SessionArtifact


class ReviewResult:
    """Result of a review operation."""

    def __init__(
        self,
        approved: bool,
        feedback: str | None = None,
        edited_content: str | None = None,
    ) -> None:
        """Initialize review result.

        Args:
            approved: Whether the artifact was approved.
            feedback: Optional feedback from reviewer.
            edited_content: Optional edited content (for file-based review).
        """
        self.approved = approved
        self.feedback = feedback
        self.edited_content = edited_content


class BaseReviewHandler(ABC):
    """Abstract base class for review handlers."""

    @abstractmethod
    async def review(
        self,
        session: Session,
        agent_name: str,
        artifact: SessionArtifact,
    ) -> ReviewResult:
        """Perform a review of an artifact.

        Args:
            session: Current workflow session.
            agent_name: Name of the agent that produced the artifact.
            artifact: The artifact to review.

        Returns:
            ReviewResult with the review decision.
        """
