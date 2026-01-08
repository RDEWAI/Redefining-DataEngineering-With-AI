"""Session detail page for PWI Dashboard.

Shows detailed information about a single session including
workflow progress, artifacts, and review history.
"""

from __future__ import annotations

from nicegui import ui

from pwi.dashboard.app import get_session_manager
from pwi.dashboard.components.csv_viewer import csv_table
from pwi.dashboard.components.markdown_viewer import markdown_with_mermaid
from pwi.workflow.session import Session
from pwi.workflow.states import AGENT_ORDER, WorkflowState


def _render_artifact_content(
    artifact_format: str,
    content: str,
    max_height: str = "600px",
    is_modal: bool = False,
) -> None:
    """Render artifact content based on format.

    Args:
        artifact_format: The format of the artifact (markdown, csv, yaml).
        content: The artifact content.
        max_height: Maximum height for the viewer.
        is_modal: Whether rendering in a modal (affects sizing).
    """
    if artifact_format == "markdown":
        markdown_with_mermaid(
            content=content,
            max_height=max_height,
            show_raw_toggle=True,
        )
    elif artifact_format == "csv":
        # Use CSV table viewer with gridlines
        csv_table(
            content=content,
            max_height=max_height,
            rows_per_page=50 if is_modal else 25,
        )
    else:
        # Use code display for other formats (yaml, etc.)
        language = "yaml" if artifact_format == "yaml" else "text"
        ui.code(content[:10000], language=language).classes("w-full").style(
            f"max-height: {max_height}; overflow: auto;"
        )
        if len(content) > 10000:
            ui.label(f"... ({len(content) - 10000:,} more characters)").classes(
                "text-grey text-sm"
            )


def _create_maximize_modal(
    artifact_type: str,
    artifact_format: str,
    content: str,
    version: int,
) -> ui.dialog:
    """Create a maximize modal dialog for artifact content.

    Args:
        artifact_type: Type of artifact (drd, pad, dmd, etc.).
        artifact_format: Format of the artifact.
        content: The artifact content.
        version: Artifact version number.

    Returns:
        The dialog element.
    """
    # Create overlay dialog (not maximized) with large dimensions
    with ui.dialog() as dialog:
        dialog.props('persistent')

        with ui.card().classes("modal-card").style(
            "width: 90vw; max-width: 1400px; height: 85vh; "
            "display: flex; flex-direction: column;"
        ):
            # Modal header - fixed height
            with ui.row().classes("w-full items-center p-3 bg-grey-2").style(
                "flex-shrink: 0;"
            ):
                ui.label(f"{artifact_type.upper()}").classes("text-h6 text-bold")
                ui.space()
                ui.label(f"v{version}").classes("text-grey")
                ui.label(f"| {artifact_format}").classes("text-grey")
                ui.label(f"| {len(content):,} chars").classes("text-grey")
                ui.button(icon="close", on_click=dialog.close).props(
                    "flat round dense"
                )

            # Modal content - fills remaining space
            with ui.column().classes("w-full p-4").style(
                "flex: 1; overflow: hidden; min-height: 0;"
            ):
                _render_artifact_content(
                    artifact_format=artifact_format,
                    content=content,
                    max_height="calc(85vh - 100px)",
                    is_modal=True,
                )

    return dialog


def get_agent_status(session: Session, agent_name: str) -> tuple[str, str]:
    """Get status icon and color for an agent.

    Returns:
        Tuple of (icon, color).
    """
    # Check if artifact exists
    artifact_types = {
        "data_analyst": "drd",
        "data_architect": "pad",
        "mapping_engineer": "dmd",
        "dq_engineer": "dqs",
        "story_writer": "stories",
        "sync_agent": "package",
    }
    artifact_type = artifact_types.get(agent_name)

    if artifact_type and artifact_type in session.artifacts:
        return "check_circle", "positive"

    # Check current state
    state = session.get_state()
    if state.value.startswith(agent_name):
        if "_running" in state.value:
            return "sync", "primary"
        if "_review" in state.value:
            return "pending", "warning"

    return "radio_button_unchecked", "grey"


@ui.page("/session/{session_id}")
def session_detail_page(session_id: str) -> None:
    """Render the session detail page."""
    session_manager = get_session_manager()

    if not session_manager:
        ui.label("Session manager not initialized").classes("text-negative")
        return

    if not session_manager.exists(session_id):
        ui.label(f"Session not found: {session_id}").classes("text-negative")
        return

    session = session_manager.load(session_id)
    state = session.get_state()

    # Header
    with ui.header().classes("bg-primary"):
        ui.button(icon="arrow_back", on_click=lambda: ui.navigate.to("/")).props(
            "flat color=white"
        )
        ui.label(f"Session: {session_id}").classes("text-h5 text-white")
        ui.space()

    with ui.column().classes("w-full max-w-6xl mx-auto p-4"):
        # Status card
        state_color = (
            "positive"
            if state == WorkflowState.COMPLETED
            else "negative"
            if state == WorkflowState.FAILED
            else "warning"
            if state == WorkflowState.PAUSED
            else "primary"
        )

        with ui.card().classes("w-full p-4"):
            with ui.row().classes("w-full items-center"):
                ui.label("Status").classes("text-h6")
                ui.space()
                ui.badge(state.value, color=state_color)

            with ui.row().classes("w-full gap-8 mt-4"):
                with ui.column():
                    ui.label("Project").classes("text-grey text-sm")
                    ui.label(session.project_name or "-")

                with ui.column():
                    ui.label("Created").classes("text-grey text-sm")
                    ui.label(session.created_at.strftime("%Y-%m-%d %H:%M"))

                with ui.column():
                    ui.label("Updated").classes("text-grey text-sm")
                    ui.label(session.updated_at.strftime("%Y-%m-%d %H:%M"))

                with ui.column():
                    ui.label("Tokens").classes("text-grey text-sm")
                    ui.label(f"{session.get_total_tokens():,}")

                with ui.column():
                    ui.label("Cost").classes("text-grey text-sm")
                    ui.label(session.get_formatted_cost())

        if session.error_message:
            with ui.card().classes("w-full p-4 bg-red-50"):
                ui.label("Error").classes("text-negative text-bold")
                ui.label(session.error_message).classes("text-negative")

        # Workflow progress
        ui.label("Workflow Progress").classes("text-h6 mt-4")
        with ui.card().classes("w-full p-4"):
            with ui.stepper().props("vertical").classes("w-full"):
                for agent_name in AGENT_ORDER:
                    icon, color = get_agent_status(session, agent_name)
                    display_name = agent_name.replace("_", " ").title()

                    with ui.step(display_name, icon=icon).props(f"color={color}"):
                        artifact_types = {
                            "data_analyst": "drd",
                            "data_architect": "pad",
                            "mapping_engineer": "dmd",
                            "dq_engineer": "dqs",
                            "story_writer": "stories",
                            "sync_agent": "package",
                        }
                        artifact_type = artifact_types.get(agent_name)

                        if artifact_type and artifact_type in session.artifacts:
                            artifact = session.artifacts[artifact_type]
                            ui.label(
                                f"✓ {artifact_type.upper()} v{artifact.version}"
                            ).classes("text-positive")
                        else:
                            ui.label("Pending").classes("text-grey")

        # Artifacts
        if session.artifacts:
            ui.label("Artifacts").classes("text-h6 mt-4")
            with ui.tabs().classes("w-full") as tabs:
                for artifact_type in session.artifacts:
                    ui.tab(artifact_type.upper())

            # Get session manager for file-based artifact reading
            session_manager = get_session_manager()

            with ui.tab_panels(
                tabs, value=list(session.artifacts.keys())[0].upper()
            ).classes("w-full"):
                for artifact_type, artifact in session.artifacts.items():
                    # Load content from file if file-based, otherwise use inline
                    content = session.read_artifact_content(
                        session_manager.session_dir, artifact_type
                    )
                    if not content:
                        content = artifact.content  # Fallback to inline

                    with ui.tab_panel(artifact_type.upper()):
                        with ui.card().classes("w-full"):
                            # Header with maximize button
                            with ui.row().classes("w-full items-center p-2 bg-grey-2"):
                                ui.label(f"{artifact_type.upper()}").classes("text-bold")
                                ui.space()
                                ui.label(f"v{artifact.version}").classes("text-grey")
                                ui.label(f"| {artifact.format}").classes("text-grey")
                                ui.label(
                                    f"| {len(content):,} chars" if content else "| empty"
                                ).classes("text-grey")
                                if artifact.is_file_based:
                                    ui.label("| file-based").classes("text-grey text-xs")

                                # Create modal for this artifact
                                modal = _create_maximize_modal(
                                    artifact_type=artifact_type,
                                    artifact_format=artifact.format,
                                    content=content or "",
                                    version=artifact.version,
                                )

                                # Maximize button
                                ui.button(
                                    icon="open_in_full",
                                    on_click=modal.open,
                                ).props("flat round dense").tooltip("Maximize")

                            # Inline content viewer
                            with ui.column().classes("w-full p-2"):
                                _render_artifact_content(
                                    artifact_format=artifact.format,
                                    content=content or "[No content available]",
                                    max_height="600px",
                                    is_modal=False,
                                )

        # Token usage breakdown
        if session.token_usage:
            ui.label("Token Usage").classes("text-h6 mt-4")
            with ui.card().classes("w-full p-4"):
                columns = [
                    {"name": "agent", "label": "Agent", "field": "agent"},
                    {"name": "model", "label": "Model", "field": "model"},
                    {"name": "prompt", "label": "Prompt", "field": "prompt"},
                    {"name": "completion", "label": "Completion", "field": "completion"},
                    {"name": "total", "label": "Total", "field": "total"},
                    {"name": "cost", "label": "Cost", "field": "cost"},
                ]
                rows = [
                    {
                        "agent": usage.agent,
                        "model": usage.model,
                        "prompt": f"{usage.prompt_tokens:,}",
                        "completion": f"{usage.completion_tokens:,}",
                        "total": f"{usage.total_tokens:,}",
                        "cost": f"${usage.cost_usd}",
                    }
                    for usage in session.token_usage
                ]
                ui.table(columns=columns, rows=rows, row_key="agent").classes("w-full")

        # Review history
        if session.reviews:
            ui.label("Review History").classes("text-h6 mt-4")
            with ui.card().classes("w-full p-4"):
                columns = [
                    {"name": "agent", "label": "Agent", "field": "agent"},
                    {"name": "decision", "label": "Decision", "field": "decision"},
                    {"name": "timestamp", "label": "Timestamp", "field": "timestamp"},
                    {"name": "feedback", "label": "Feedback", "field": "feedback"},
                ]
                rows = [
                    {
                        "agent": review.agent,
                        "decision": "✓ Approved" if review.approved else "✗ Rejected",
                        "timestamp": review.reviewed_at.strftime("%Y-%m-%d %H:%M:%S"),
                        "feedback": review.feedback or "-",
                    }
                    for review in session.reviews
                ]
                ui.table(columns=columns, rows=rows, row_key="agent").classes("w-full")
