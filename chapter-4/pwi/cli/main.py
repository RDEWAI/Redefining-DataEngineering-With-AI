"""CLI entry point for Planning with Intent.

This module provides the main CLI application using Typer.
"""

from __future__ import annotations

import typer
from rich.console import Console

from pwi import __version__
from pwi.cli.commands import generate, init, plan, review, session

# Create the main app
app = typer.Typer(
    name="pwi",
    help="Planning with Intent - Transform business requests into Data Engineering artifacts",
    add_completion=True,
    rich_markup_mode="rich",
)

# Create console for rich output
console = Console()

# Register subcommand groups
app.add_typer(init.app, name="init", help="Initialize a new PWI project")
app.add_typer(plan.app, name="plan", help="Run planning workflow on a request")
app.add_typer(generate.app, name="generate", help="Generate specific artifacts")
app.add_typer(session.app, name="session", help="Manage workflow sessions")
app.add_typer(review.app, name="review", help="Review and approve artifacts")


@app.command()
def dashboard(
    port: int = typer.Option(8080, help="Port to run dashboard on"),
    host: str = typer.Option("127.0.0.1", help="Host to bind to"),
) -> None:
    """Start the NiceGUI web dashboard."""
    console.print(f"[bold blue]Starting PWI Dashboard on http://{host}:{port}[/bold blue]")
    try:
        from pwi.dashboard.app import run_dashboard

        run_dashboard(host=host, port=port)
    except ImportError:
        console.print(
            "[red]Dashboard dependencies not installed. "
            "Install with: pip install nicegui[/red]"
        )
        raise typer.Exit(1)


@app.command()
def version() -> None:
    """Show PWI version."""
    console.print(f"[bold]PWI[/bold] version [green]{__version__}[/green]")


@app.command("completion")
def shell_completion(
    shell: str = typer.Argument(
        None,
        help="Shell type: bash, zsh, fish, powershell",
    ),
    install: bool = typer.Option(
        False,
        "--install",
        "-i",
        help="Install completion to shell config",
    ),
) -> None:
    """Generate or install shell completion scripts.

    Examples:

        # Show completion script for bash
        pwi completion bash

        # Install completion for zsh
        pwi completion zsh --install

        # Manual installation
        pwi completion bash >> ~/.bashrc
    """
    import subprocess
    import sys

    if shell is None:
        console.print("[bold]Shell Completion[/bold]\n")
        console.print("Generate shell completion scripts for pwi.\n")
        console.print("[bold]Usage:[/bold]")
        console.print("  pwi completion [SHELL]           Show completion script")
        console.print("  pwi completion [SHELL] --install Install to shell config\n")
        console.print("[bold]Supported shells:[/bold]")
        console.print("  bash, zsh, fish, powershell\n")
        console.print("[bold]Examples:[/bold]")
        console.print("  pwi completion bash >> ~/.bashrc")
        console.print("  pwi completion zsh --install")
        return

    shell = shell.lower()
    valid_shells = ["bash", "zsh", "fish", "powershell"]

    if shell not in valid_shells:
        console.print(f"[red]Unknown shell: {shell}[/red]")
        console.print(f"Supported shells: {', '.join(valid_shells)}")
        raise typer.Exit(1)

    if install:
        # Use typer's built-in completion installation
        try:
            subprocess.run(
                [sys.executable, "-m", "typer", "pwi.cli.main:app", "--install-completion", shell],
                check=True,
            )
            console.print(f"[green]Completion installed for {shell}![/green]")
            console.print("Restart your shell or source your config file to enable.")
        except subprocess.CalledProcessError:
            console.print(f"[red]Failed to install completion for {shell}[/red]")
            raise typer.Exit(1)
    else:
        # Show the completion script
        try:
            result = subprocess.run(
                [sys.executable, "-m", "typer", "pwi.cli.main:app", "--show-completion", shell],
                capture_output=True,
                text=True,
                check=True,
            )
            console.print(result.stdout)
        except subprocess.CalledProcessError:
            console.print(f"[red]Failed to generate completion for {shell}[/red]")
            raise typer.Exit(1)


@app.callback()
def main_callback(
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable verbose output"),
    json_logs: bool = typer.Option(False, "--json-logs", help="Output logs in JSON format"),
    log_file: str = typer.Option(None, "--log-file", help="Write logs to file"),
) -> None:
    """Planning with Intent - Data Engineering workflow automation."""
    from pwi.utils.logging import setup_logging

    level = "DEBUG" if verbose else "INFO"
    setup_logging(level=level, json_output=json_logs, log_file=log_file)


def main() -> None:
    """Main entry point."""
    app()


if __name__ == "__main__":
    main()
