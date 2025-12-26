"""Unified MCP Client with Configuration and Assistant.

This module provides a unified entry point for the MCP client that:
1. Configures code execution mode (on by default) vs traditional JSON tools
2. Toggles features like RAG and dummy tools
3. Provides both interactive menu and CLI flag interfaces
4. Launches the EnhancedLibraryAssistant with the configured settings

Usage:
    # Interactive mode (shows settings menu)
    python -m src.mcp.client

    # Direct chat (skips menu, code execution enabled by default)
    python -m src.mcp.client --no-menu

    # With CLI flags
    python -m src.mcp.client --no-menu --rag
    python -m src.mcp.client --no-menu --no-code-execution  # Traditional mode
    python -m src.mcp.client --no-menu --dummy-tools

    # Interactive menu with pre-configured settings
    python -m src.mcp.client -i --no-code-execution
"""

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

# Add chapter-3 to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from dotenv import load_dotenv

# Load .env from chapter-3 directory
env_path = Path(__file__).parent.parent.parent / ".env"
load_dotenv(env_path, override=True)

# Config file path (in chapter-3 directory)
CONFIG_FILE = Path(__file__).parent.parent.parent / ".mcp_config.json"


@dataclass
class MCPClientConfig:
    """Configuration for MCP Client.

    Attributes:
        enable_code_execution: Enable code execution mode (default True, token efficient)
        enable_rag: Enable semantic search/RAG functionality
        enable_dummy_tools: Enable 100 enterprise dummy tools for scale testing
        show_tool_calls: Display tool calls/generated code during execution
        verbose: Enable verbose debug output
    """

    enable_code_execution: bool = True
    enable_rag: bool = False
    enable_dummy_tools: bool = False
    show_tool_calls: bool = True
    verbose: bool = False

    @property
    def mode(self) -> str:
        """Get mode string for compatibility."""
        return "code_execution" if self.enable_code_execution else "traditional"

    def save(self) -> None:
        """Save configuration to disk."""
        CONFIG_FILE.write_text(json.dumps(asdict(self), indent=2))

    @classmethod
    def load(cls) -> "MCPClientConfig":
        """Load configuration from disk, or return defaults if not found."""
        if CONFIG_FILE.exists():
            try:
                data = json.loads(CONFIG_FILE.read_text())
                return cls(**data)
            except (json.JSONDecodeError, TypeError):
                # Invalid config file, return defaults
                pass
        return cls()


class MCPClient:
    """Unified MCP Client with configuration and assistant.

    This client provides:
    - Configuration management for execution mode and features
    - Interactive settings menu
    - Integration with EnhancedLibraryAssistant

    Example:
        >>> config = MCPClientConfig(mode="code_execution", enable_rag=True)
        >>> client = MCPClient(config)
        >>> client.run()
    """

    def __init__(self, config: MCPClientConfig | None = None):
        """Initialize MCP Client.

        Args:
            config: Configuration settings. Uses defaults if not provided.
        """
        self.config = config or MCPClientConfig()
        self._assistant = None

    def show_settings_menu(self) -> bool:
        """Display interactive settings menu.

        Returns:
            True to continue and run assistant, False to quit.
        """
        while True:
            # Clear screen (optional, works on most terminals)
            print("\033[H\033[J", end="")

            code_exec_status = "ON" if self.config.enable_code_execution else "OFF"
            rag_status = "ON" if self.config.enable_rag else "OFF"
            dummy_status = "ON" if self.config.enable_dummy_tools else "OFF"
            tools_status = "ON" if self.config.show_tool_calls else "OFF"

            print("=" * 50)
            print("       MCP Client Settings")
            print("=" * 50)
            print()
            print(f"  [1] Code Execution: {code_exec_status}")
            print(f"  [2] RAG (Semantic Search): {rag_status}")
            print(f"  [3] Dummy Tools (100 enterprise): {dummy_status}")
            print(f"  [4] Show Tool Calls: {tools_status}")
            print()
            print("-" * 50)
            print("  [Enter] Start Assistant")
            print("  [q] Quit")
            print("=" * 50)
            print()

            try:
                choice = input("Select option: ").strip().lower()
            except (EOFError, KeyboardInterrupt):
                print("\n")
                return False

            if choice == "":
                # Save and start assistant
                self.config.save()
                return True
            elif choice == "q":
                return False
            elif choice == "1":
                # Toggle code execution
                self.config.enable_code_execution = not self.config.enable_code_execution
                self.config.save()
            elif choice == "2":
                self.config.enable_rag = not self.config.enable_rag
                self.config.save()
            elif choice == "3":
                self.config.enable_dummy_tools = not self.config.enable_dummy_tools
                self.config.save()
            elif choice == "4":
                self.config.show_tool_calls = not self.config.show_tool_calls
                self.config.save()
            else:
                print(f"Unknown option: {choice}")
                input("Press Enter to continue...")

    def _create_assistant(self):
        """Create the EnhancedLibraryAssistant with current config."""
        from src.agentic.agents.library_assistant_enhanced import EnhancedLibraryAssistant
        from src.agentic.llm.unified_client import UnifiedLLMClient

        # Initialize LLM client
        llm = UnifiedLLMClient.from_env()

        # Create assistant with config
        self._assistant = EnhancedLibraryAssistant(
            llm_provider=llm,
            mode=self.config.mode,
            verbose=self.config.verbose,
            show_tool_calls=self.config.show_tool_calls,
            enable_rag=self.config.enable_rag,
            enable_dummy_tools=self.config.enable_dummy_tools,
        )

    def run_assistant(self) -> None:
        """Run the assistant interactive loop (pure chat interface)."""
        if self._assistant is None:
            self._create_assistant()

        code_exec_status = "ON" if self.config.enable_code_execution else "OFF"
        rag_status = "ON" if self.config.enable_rag else "OFF"
        dummy_status = "ON" if self.config.enable_dummy_tools else "OFF"

        print()
        print("=" * 60)
        print("MCP Library Assistant")
        print("=" * 60)
        print(f"  Code Execution: {code_exec_status}")
        print(f"  RAG: {rag_status}")
        print(f"  Dummy Tools: {dummy_status}")
        print("-" * 60)
        print()
        print("Ask questions about the library!")
        print("Type 'quit' or press Ctrl+C to exit.")
        print("-" * 60)

        while True:
            try:
                user_input = input("\nYou: ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\n\nGoodbye!")
                break

            if not user_input:
                continue

            # Exit commands
            if user_input.lower() in ("quit", "exit", "q"):
                print("Goodbye!")
                break

            # Process query
            try:
                response = self._assistant.query(user_input)
                print(f"\nAssistant: {response}")
            except Exception as e:
                print(f"\nError: {e}")
                if self.config.verbose:
                    import traceback

                    traceback.print_exc()

    def run(self, interactive: bool = True) -> None:
        """Run the MCP Client.

        Args:
            interactive: If True, show settings menu first. If False, start assistant directly.
        """
        if interactive:
            should_continue = self.show_settings_menu()
            if not should_continue:
                print("Goodbye!")
                return

        try:
            self.run_assistant()
        except Exception as e:
            print(f"Error: {e}")
            print()
            print("Please ensure your LLM configuration is set in .env:")
            print("  LLM_BASE_URL=your-api-base-url")
            print("  LLM_API_KEY=your-api-key")
            print("  LLM_MODEL=your-model-name")
            sys.exit(1)


def main() -> None:
    """Entry point for MCP client."""
    parser = argparse.ArgumentParser(
        description="Unified MCP Client - Configuration & Assistant",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m src.mcp.client                       # Interactive settings menu
  python -m src.mcp.client --no-menu             # Start assistant directly
  python -m src.mcp.client --no-menu --rag       # Start with RAG enabled
  python -m src.mcp.client --no-menu --no-code-execution  # Traditional mode
  python -m src.mcp.client -i --no-code-execution  # Menu with code exec disabled
        """,
    )
    parser.add_argument(
        "--code-execution",
        action="store_true",
        default=True,
        dest="code_execution",
        help="Enable code execution mode (default: enabled)",
    )
    parser.add_argument(
        "--no-code-execution",
        action="store_false",
        dest="code_execution",
        help="Disable code execution (use traditional JSON tools)",
    )
    parser.add_argument(
        "--rag",
        action="store_true",
        help="Enable RAG/semantic search",
    )
    parser.add_argument(
        "--dummy-tools",
        action="store_true",
        help="Enable 100 enterprise dummy tools for scale demo",
    )
    parser.add_argument(
        "--hide-tools",
        action="store_true",
        help="Hide tool calls/generated code display",
    )
    parser.add_argument(
        "-i",
        "--interactive",
        action="store_true",
        help="Show interactive settings menu",
    )
    parser.add_argument(
        "--no-menu",
        action="store_true",
        help="Skip settings menu and start assistant directly",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose debug output",
    )

    args = parser.parse_args()

    # Load saved config as base
    config = MCPClientConfig.load()

    # CLI args override saved config
    # Check if --no-code-execution was explicitly passed (code_execution will be False)
    # or if any other feature flags were explicitly passed
    if not args.code_execution:
        config.enable_code_execution = False
    if args.rag:
        config.enable_rag = True
    if args.dummy_tools:
        config.enable_dummy_tools = True
    if args.hide_tools:
        config.show_tool_calls = False
    if args.verbose:
        config.verbose = True

    # Create client
    client = MCPClient(config)

    # Determine if we should show interactive menu
    # --no-menu: skip menu, start assistant directly
    # -i/--interactive: always show menu
    # Default (no flags): show menu
    if args.no_menu:
        show_menu = False
    elif args.interactive:
        show_menu = True
    else:
        # Default: show menu unless feature flags provided
        has_feature_flags = (
            args.rag or args.dummy_tools or args.hide_tools or not args.code_execution
        )
        show_menu = not has_feature_flags

    client.run(interactive=show_menu)


if __name__ == "__main__":
    main()
