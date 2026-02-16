"""NiceGUI dashboard application for Planning with Intent.

This module provides the main dashboard application and routing.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from nicegui import ui

from pwi.config.loader import load_config
from pwi.workflow.session import SessionManager

if TYPE_CHECKING:
    from pwi.config.schema import PWIConfig

# Module-level state for non-serializable objects
# NiceGUI's app.storage.general requires JSON-serializable data
_app_state: dict[str, PWIConfig | SessionManager | None] = {
    "config": None,
    "session_manager": None,
}


def get_config() -> PWIConfig | None:
    """Get the loaded configuration."""
    return _app_state.get("config")  # type: ignore[return-value]


def get_session_manager() -> SessionManager | None:
    """Get the session manager."""
    return _app_state.get("session_manager")  # type: ignore[return-value]


def run_dashboard(host: str = "127.0.0.1", port: int = 8080) -> None:
    """Run the NiceGUI dashboard.

    Args:
        host: Host to bind to.
        port: Port to run on.
    """
    # Load configuration
    config = load_config()
    session_manager = SessionManager(config.project.session_dir)

    # Store in module-level state (not NiceGUI storage, which requires JSON)
    _app_state["config"] = config
    _app_state["session_manager"] = session_manager

    # Import pages to register routes
    from pwi.dashboard.pages import home, session_detail  # noqa: F401

    # Run the app
    ui.run(
        host=host,
        port=port,
        title="PWI Dashboard",
        favicon="🗂️",
        reload=False,
        show=False,
    )
