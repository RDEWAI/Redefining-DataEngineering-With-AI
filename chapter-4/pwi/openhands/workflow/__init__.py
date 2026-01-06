"""OpenHands workflow orchestration for PWI.

This module provides the workflow orchestration layer that wraps
OpenHands AgentController with PWI-specific functionality:
- Review gates via EventStream
- Session persistence with event replay
- Sequential agent execution with dependencies

Usage:
    from pwi.openhands.workflow import (
        PWIWorkflowController,
        EventStream,
        SessionEventAdapter,
        get_review_handler,
    )

    # Create workflow controller
    controller = PWIWorkflowController(
        session=session,
        session_manager=session_manager,
        config=config,
        llm_client=llm,
        auto_approve=False,
    )

    # Run the workflow
    success = await controller.run()
"""

from pwi.openhands.workflow.events import (
    # Event types
    PWIEvent,
    PWIEventType,
    # Workflow events
    WorkflowStartedEvent,
    WorkflowPausedEvent,
    WorkflowResumedEvent,
    WorkflowCompletedEvent,
    WorkflowFailedEvent,
    # Agent events
    AgentStartedEvent,
    AgentCompletedEvent,
    AgentFailedEvent,
    AgentToolCallEvent,
    AgentToolResultEvent,
    # Review events
    ReviewPendingEvent,
    ReviewApprovedEvent,
    ReviewRejectedEvent,
    ReviewTimeoutEvent,
    # Artifact events
    ArtifactGeneratedEvent,
    ArtifactValidatedEvent,
    ArtifactSavedEvent,
    # User events
    UserInputEvent,
    UserFeedbackEvent,
    # Stream
    EventStream,
)
from pwi.openhands.workflow.session_adapter import SessionEventAdapter
from pwi.openhands.workflow.review_handler import (
    BaseReviewHandler,
    CLIReviewHandler,
    FileReviewHandler,
    AutoApproveHandler,
    SkipReviewHandler,
    ReviewResult,
    get_review_handler,
)
from pwi.openhands.workflow.controller import PWIWorkflowController


__all__ = [
    # Controller
    "PWIWorkflowController",
    # Events
    "PWIEvent",
    "PWIEventType",
    "WorkflowStartedEvent",
    "WorkflowPausedEvent",
    "WorkflowResumedEvent",
    "WorkflowCompletedEvent",
    "WorkflowFailedEvent",
    "AgentStartedEvent",
    "AgentCompletedEvent",
    "AgentFailedEvent",
    "AgentToolCallEvent",
    "AgentToolResultEvent",
    "ReviewPendingEvent",
    "ReviewApprovedEvent",
    "ReviewRejectedEvent",
    "ReviewTimeoutEvent",
    "ArtifactGeneratedEvent",
    "ArtifactValidatedEvent",
    "ArtifactSavedEvent",
    "UserInputEvent",
    "UserFeedbackEvent",
    "EventStream",
    # Session adapter
    "SessionEventAdapter",
    # Review handlers
    "BaseReviewHandler",
    "CLIReviewHandler",
    "FileReviewHandler",
    "AutoApproveHandler",
    "SkipReviewHandler",
    "ReviewResult",
    "get_review_handler",
]
