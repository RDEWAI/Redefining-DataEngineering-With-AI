"""Home page for PWI Dashboard.

Shows list of all sessions with status and quick actions.
"""

from __future__ import annotations

from typing import Any

from nicegui import ui

from pwi.dashboard.app import get_session_manager
from pwi.workflow.states import WorkflowState


def get_state_color(state: WorkflowState) -> str:
    """Get color for state badge."""
    colors = {
        WorkflowState.COMPLETED: "positive",
        WorkflowState.FAILED: "negative",
        WorkflowState.PAUSED: "warning",
        WorkflowState.CANCELLED: "grey",
    }
    return colors.get(state, "primary")


@ui.page("/")
def home_page() -> None:
    """Render the home page with session list."""
    session_manager = get_session_manager()

    with ui.header().classes("bg-primary"):
        ui.label("PWI Dashboard").classes("text-h5 text-white")
        ui.space()
        ui.button(
            "Refresh",
            icon="refresh",
            on_click=lambda: ui.navigate.to("/"),
        ).props("flat color=white")

    with ui.column().classes("w-full max-w-6xl mx-auto p-4"):
        ui.label("Sessions").classes("text-h6")

        if not session_manager:
            ui.label("Session manager not initialized").classes("text-negative")
            return

        sessions = session_manager.list_sessions()

        if not sessions:
            with ui.card().classes("w-full p-4"):
                ui.label("No sessions found").classes("text-grey")
                ui.label("Run 'pwi plan run <request.md>' to start a workflow").classes(
                    "text-sm text-grey"
                )
            return

        # Session table
        columns: list[dict[str, Any]] = [
            {"name": "id", "label": "Session ID", "field": "id", "sortable": True},
            {"name": "project", "label": "Project", "field": "project", "sortable": True},
            {"name": "state", "label": "State", "field": "state", "sortable": True},
            {"name": "created", "label": "Created", "field": "created", "sortable": True},
            {"name": "artifacts", "label": "Artifacts", "field": "artifacts"},
            {"name": "tokens", "label": "Tokens", "field": "tokens", "sortable": True},
            {"name": "cost", "label": "Cost", "field": "cost"},
            {"name": "actions", "label": "Actions", "field": "actions"},
        ]

        rows = []
        for session in sessions:
            state = session.get_state()
            rows.append(
                {
                    "id": session.session_id,
                    "project": session.project_name or "-",
                    "state": state.value,
                    "created": session.created_at.strftime("%Y-%m-%d %H:%M"),
                    "artifacts": len(session.artifacts),
                    "tokens": f"{session.get_total_tokens():,}",
                    "cost": session.get_formatted_cost(),
                }
            )

        table = ui.table(
            columns=columns,
            rows=rows,
            row_key="id",
            pagination={"rowsPerPage": 10},
        ).classes("w-full")

        table.add_slot(
            "body-cell-state",
            """
            <q-td :props="props">
                <q-badge :color="props.value === 'completed' ? 'positive' :
                                 props.value === 'failed' ? 'negative' :
                                 props.value === 'paused' ? 'warning' : 'primary'">
                    {{ props.value }}
                </q-badge>
            </q-td>
            """,
        )

        table.add_slot(
            "body-cell-actions",
            """
            <q-td :props="props">
                <q-btn flat dense icon="visibility" @click="$parent.$emit('view', props.row)" />
            </q-td>
            """,
        )

        table.on("view", lambda e: ui.navigate.to(f"/session/{e.args['id']}"))

        # Quick stats
        with ui.row().classes("w-full gap-4 mt-4"):
            completed = sum(1 for s in sessions if s.get_state() == WorkflowState.COMPLETED)
            failed = sum(1 for s in sessions if s.get_state() == WorkflowState.FAILED)
            paused = sum(1 for s in sessions if s.get_state() == WorkflowState.PAUSED)

            with ui.card().classes("p-4"):
                ui.label(str(completed)).classes("text-h4 text-positive")
                ui.label("Completed").classes("text-grey")

            with ui.card().classes("p-4"):
                ui.label(str(failed)).classes("text-h4 text-negative")
                ui.label("Failed").classes("text-grey")

            with ui.card().classes("p-4"):
                ui.label(str(paused)).classes("text-h4 text-warning")
                ui.label("Paused").classes("text-grey")

            with ui.card().classes("p-4"):
                ui.label(str(len(sessions))).classes("text-h4 text-primary")
                ui.label("Total").classes("text-grey")
