"""Unified MCP Client with Configuration and Assistant.

This module provides a unified entry point for the MCP client that:
1. Configures code execution mode (off by default) vs traditional JSON tools
2. Toggles features like RAG and dummy tools
3. Provides both interactive menu and CLI flag interfaces
4. Launches the EnhancedLibraryAssistant with the configured settings

Usage:
    # Interactive mode (shows settings menu)
    python -m src.mcp.client

    # Direct chat (skips menu, code execution disabled by default)
    python -m src.mcp.client --no-menu

    # With CLI flags
    python -m src.mcp.client --no-menu --rag
    python -m src.mcp.client --no-menu --code-execution  # Code execution mode
    python -m src.mcp.client --no-menu --dummy-tools

    # Interactive menu with pre-configured settings
    python -m src.mcp.client -i --code-execution
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
        enable_code_execution: Enable code execution mode (default False)
        enable_rag: Enable RAG functionality (semantic search + sales data tools).
                   When enabled: semantic_search, search_sales, get_book_sales,
                   get_sales_stats, get_top_selling_books, search_sales_semantic.
                   When disabled: only basic library tools are available.
        enable_dummy_tools: Enable 100 enterprise dummy tools for scale testing
        show_tool_calls: Display tool calls/generated code during execution
        verbose: Enable verbose debug output
    """

    enable_code_execution: bool = False
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
    - Interactive commands: /tools, /stats, /resources, /help

    Example:
        >>> config = MCPClientConfig(mode="code_execution", enable_rag=True)
        >>> client = MCPClient(config)
        >>> client.run()
    """

    # Available MCP tools (book tools + sales tools)
    MCP_TOOLS = [
        # Book tools
        ("search_books", "Search books by title, author, or keyword"),
        ("get_book_details", "Get complete details for a specific book"),
        ("check_availability", "Check if a book is available and get location"),
        ("list_by_category", "List all books in a specific category"),
        ("list_by_status", "List all books with a specific status"),
        ("locate_book", "Get physical location of a book"),
        ("find_books_in_cabinet", "List books in a specific cabinet"),
        ("get_weak_signal_books", "Get books with weak RFID signals"),
        # Sales tools
        ("search_sales", "Search sales with filters (book, segment, region, channel)"),
        ("get_book_sales", "Get all sales for a specific book"),
        ("get_sales_stats", "Get aggregate sales statistics"),
        ("get_top_selling_books", "Get best-selling books by quantity"),
        ("get_sales_by_month", "Get monthly sales for trend analysis"),
    ]

    # Available MCP resources (from library_server.py)
    MCP_RESOURCES = [
        ("library://stats", "Aggregate library statistics"),
        ("library://missing_books", "List of all missing books"),
        ("library://location_map", "Location map with book counts"),
        ("library://sales_stats", "Aggregate sales statistics"),
    ]

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
            print(f"  [2] RAG (Semantic Search + Sales): {rag_status}")
            print(f"  [3] Dummy Tools (100 enterprise): {dummy_status}")
            print(f"  [4] Show Tool Calls: {tools_status}")
            print()
            print("-" * 50)
            print("  [Enter] Start Assistant")
            print("  [m] Monitor MCP (show available commands)")
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
                # Apply config changes to existing assistant
                if self._assistant is not None:
                    # Update RAG setting
                    if self._assistant.is_rag_enabled() != self.config.enable_rag:
                        self._assistant.set_rag_enabled(self.config.enable_rag)
                    # Update dummy tools setting
                    if self._assistant.is_dummy_tools_enabled() != self.config.enable_dummy_tools:
                        self._assistant.set_dummy_tools_enabled(self.config.enable_dummy_tools)
                    # Update mode if changed
                    new_mode = (
                        "code_execution" if self.config.enable_code_execution else "traditional"
                    )
                    if self._assistant.get_mode() != new_mode:
                        self._assistant.set_mode(new_mode)
                        self._assistant.reset_conversation()
                    # Update tool call display
                    self._assistant._show_tool_calls = self.config.show_tool_calls
                return True
            elif choice == "q":
                return False
            elif choice == "m":
                self._show_monitor_mcp()
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

    def _show_monitor_mcp(self) -> None:
        """Interactive MCP monitor with command execution."""
        # Ensure assistant is created for command execution
        if self._assistant is None:
            self._create_assistant()

        while True:
            print("\033[H\033[J", end="")  # Clear screen
            self._display_monitor_header()

            try:
                user_input = input("\nMonitor> ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\n")
                return

            if not user_input:
                continue

            # Return to main menu
            if user_input.lower() in ("back", "menu", "b", "m", "/menu", "/back"):
                return

            # Exit completely
            if user_input.lower() in ("quit", "exit", "q", "/quit", "/exit"):
                print("Goodbye!")
                sys.exit(0)

            # Handle slash commands
            if user_input.startswith("/"):
                cmd = user_input.lower()

                if cmd == "/help":
                    self._show_help()
                elif cmd == "/tools":
                    self._show_tools()
                elif cmd == "/stats":
                    self._show_stats()
                elif cmd == "/resources":
                    self._show_resources()
                elif cmd == "/settings":
                    self._show_settings()
                elif cmd == "/clear":
                    self._clear_conversation()
                elif cmd == "/code":
                    self._toggle_code_execution()
                elif cmd == "/rag":
                    self._toggle_rag()
                elif cmd == "/dummy":
                    self._toggle_dummy_tools()
                else:
                    print(f"Unknown command: {user_input}")
                    print("Type /help for available commands")

                input("\nPress Enter to continue...")
                continue

            # Process as a query to the assistant
            try:
                print("\nProcessing query...")
                response = self._assistant.query(user_input)
                print(f"\nAssistant: {response}")
            except Exception as e:
                print(f"\nError: {e}")
                if self.config.verbose:
                    import traceback

                    traceback.print_exc()

            input("\nPress Enter to continue...")

    def _display_monitor_header(self) -> None:
        """Display the monitor header with available commands."""
        code_status = "ON" if self.config.enable_code_execution else "OFF"
        rag_status = "ON" if self.config.enable_rag else "OFF"
        dummy_status = "ON" if self.config.enable_dummy_tools else "OFF"

        print("=" * 60)
        print("       MCP Monitor - Interactive Mode")
        print("=" * 60)
        print(f"  Code Execution: {code_status} | RAG: {rag_status} | Dummy Tools: {dummy_status}")
        print("-" * 60)
        print()
        print("Commands:")
        print("  /help       - Show all available commands")
        print("  /tools      - Toggle tool display & list MCP tools")
        print("  /stats      - Show token usage statistics")
        print("  /resources  - List available MCP resources")
        print("  /settings   - Show current configuration")
        print("  /code       - Toggle code execution ON/OFF")
        print("  /rag        - Toggle RAG (semantic search + sales)")
        print("  /dummy      - Toggle 100 dummy tools")
        print("  /clear      - Clear conversation history")
        print()
        print("Navigation:")
        print("  back, menu  - Return to main settings menu")
        print("  quit        - Exit the application")
        print()
        print("Or type a query to ask the library assistant.")
        print("-" * 60)
        print()
        print(
            f"MCP Tools ({len(self.MCP_TOOLS)}):",
            ", ".join(t[0] for t in self.MCP_TOOLS[:4]),
            "...",
        )
        print(
            f"MCP Resources ({len(self.MCP_RESOURCES)}):",
            ", ".join(r[0].split("://")[1] for r in self.MCP_RESOURCES),
        )
        print("=" * 60)

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

    def _show_help(self) -> None:
        """Display available commands."""
        tools_status = "ON" if self.config.show_tool_calls else "OFF"
        code_status = "ON" if self.config.enable_code_execution else "OFF"
        rag_status = "ON" if self.config.enable_rag else "OFF"
        dummy_status = "ON" if self.config.enable_dummy_tools else "OFF"
        print()
        print("Usage:")
        print("-" * 40)
        print("  Just type your question to query the library assistant.")
        print("  Example: 'What programming books are available?'")
        print()
        print("Commands:")
        print("-" * 40)
        print(f"  /tools      - Toggle tool display ({tools_status}) & list available tools")
        print("  /stats      - Show token usage statistics")
        print("  /resources  - List available MCP resources")
        print()
        print("Configuration:")
        print("-" * 40)
        print(f"  /code       - Toggle code execution ({code_status})")
        print(f"  /rag        - Toggle RAG: semantic search + sales ({rag_status})")
        print(f"  /dummy      - Toggle 100 dummy tools ({dummy_status})")
        print("  /settings   - Show current settings")
        print()
        print("Navigation:")
        print("-" * 40)
        print("  /menu       - Return to settings menu")
        print("  /clear      - Clear conversation history")
        print("  /help       - Show this help message")
        print("  /quit       - Exit the assistant")
        print("-" * 40)

    def _show_tools(self) -> None:
        """Toggle tool display and show available tools."""
        # Toggle show_tool_calls
        self.config.show_tool_calls = not self.config.show_tool_calls
        self.config.save()

        # Update assistant if it exists
        if self._assistant is not None:
            self._assistant._show_tool_calls = self.config.show_tool_calls

        status = "ON" if self.config.show_tool_calls else "OFF"
        print()
        print(f"Tool display: {status}")
        print()
        print("Available MCP Tools:")
        print("-" * 50)
        for name, description in self.MCP_TOOLS:
            print(f"  {name:25} - {description}")
        print("-" * 50)
        print(f"  Total: {len(self.MCP_TOOLS)} tools (8 book + 5 sales)")

        if self.config.enable_dummy_tools:
            print()
            print("Enterprise Tools:")
            print("  + 100 dummy tools across 10 domains")

    def _show_stats(self) -> None:
        """Show token usage statistics."""
        if self._assistant is None:
            print("\nNo queries made yet. Start asking questions to see stats.")
            return

        usage = self._assistant.get_token_usage()
        mode = self._assistant.get_mode()
        mode_display = "Code Execution" if mode == "code_execution" else "Traditional"

        print()
        print("=" * 50)
        print("Token Usage Statistics")
        print("=" * 50)
        print(f"  Mode:              {mode_display}")
        print(f"  Queries:           {usage['query_count']}")
        print(f"  Tool calls:        {usage['tool_calls_count']}")
        print(f"  Prompt tokens:     {usage['total_prompt_tokens']:,}")
        print(f"  Completion tokens: {usage['total_completion_tokens']:,}")
        print(f"  Total tokens:      {usage['total_tokens']:,}")
        print("=" * 50)

    def _show_resources(self) -> None:
        """Show available MCP resources."""
        print()
        print("Available MCP Resources:")
        print("-" * 50)
        for uri, description in self.MCP_RESOURCES:
            print(f"  {uri:25} - {description}")
        print("-" * 50)
        print(f"  Total: {len(self.MCP_RESOURCES)} resources")

    def _show_settings(self) -> None:
        """Show current settings."""
        code_exec_status = "ON" if self.config.enable_code_execution else "OFF"
        rag_status = "ON" if self.config.enable_rag else "OFF"
        dummy_status = "ON" if self.config.enable_dummy_tools else "OFF"
        tools_status = "ON" if self.config.show_tool_calls else "OFF"

        print()
        print("Current Settings:")
        print("-" * 40)
        print(f"  Code Execution: {code_exec_status}")
        print(f"  RAG (Search + Sales): {rag_status}")
        print(f"  Dummy Tools:    {dummy_status}")
        print(f"  Tool Display:   {tools_status}")
        print("-" * 40)
        if self.config.enable_rag:
            print("  RAG includes: semantic_search, sales tools")
        else:
            print("  RAG disabled: no semantic search or sales tools")

    def _clear_conversation(self) -> None:
        """Clear conversation history and reset token counters."""
        if self._assistant is not None:
            self._assistant.reset_conversation()
        print("Conversation cleared.")

    def _toggle_code_execution(self) -> None:
        """Toggle code execution mode."""
        self.config.enable_code_execution = not self.config.enable_code_execution
        self.config.save()

        status = "ON" if self.config.enable_code_execution else "OFF"
        mode = "Code Execution" if self.config.enable_code_execution else "Traditional"
        print(f"\nCode Execution: {status}")
        print(f"  Mode: {mode}")

        # Update assistant mode
        if self._assistant is not None:
            new_mode = "code_execution" if self.config.enable_code_execution else "traditional"
            self._assistant.set_mode(new_mode)
            self._assistant.reset_conversation()
            print("  Conversation reset for new mode.")

    def _toggle_rag(self) -> None:
        """Toggle RAG (semantic search + sales data)."""
        self.config.enable_rag = not self.config.enable_rag
        self.config.save()

        status = "ON" if self.config.enable_rag else "OFF"
        print(f"\nRAG (Semantic Search + Sales): {status}")

        # Update assistant
        if self._assistant is not None:
            self._assistant.set_rag_enabled(self.config.enable_rag)

        if self.config.enable_rag:
            print("  Now available:")
            print("    - semantic_search: Natural language book search")
            print(
                "    - Sales tools: search_sales, get_book_sales, get_sales_stats, get_top_selling_books"
            )
            print("    - search_sales_semantic: Natural language sales search")
            print()
            print("  Try: 'Find books about time travel' or 'What are the top selling books?'")
        else:
            print("  Disabled: semantic_search, all sales tools")
            print("  Only basic library tools are available.")

    def _toggle_dummy_tools(self) -> None:
        """Toggle 100 enterprise dummy tools."""
        self.config.enable_dummy_tools = not self.config.enable_dummy_tools
        self.config.save()

        status = "ON" if self.config.enable_dummy_tools else "OFF"
        print(f"\nDummy Tools (100 enterprise): {status}")

        # Update assistant
        if self._assistant is not None:
            self._assistant.set_dummy_tools_enabled(self.config.enable_dummy_tools)
            tool_count = self._assistant.get_tool_count()
            print(f"  Total tools available: {tool_count}")
            if self.config.enable_dummy_tools:
                print("  Compare /stats between /code ON vs OFF for token savings.")

    def run_assistant(self) -> bool:
        """Run the assistant interactive loop (pure chat interface).

        Returns:
            True to return to main menu, False to quit completely.
        """
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
        print(f"  RAG (Search + Sales): {rag_status}")
        print(f"  Dummy Tools: {dummy_status}")
        print("-" * 60)
        print()
        print("Type your query to ask questions about the library.")
        print("Example: 'What programming books are available?'")
        print()
        print("Type /help for commands, /menu for settings, or 'quit' to exit.")
        print("-" * 60)

        while True:
            try:
                user_input = input("\nYou: ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\n\nGoodbye!")
                return False

            if not user_input:
                continue

            # Exit commands
            if user_input.lower() in ("quit", "exit", "q", "/quit", "/exit"):
                print("Goodbye!")
                return False

            # Return to menu commands
            if user_input.lower() in ("/menu", "/back", "menu", "back"):
                print("\nReturning to settings menu...")
                return True

            # Handle slash commands
            if user_input.startswith("/"):
                cmd = user_input.lower()

                if cmd == "/help":
                    self._show_help()
                elif cmd == "/tools":
                    self._show_tools()
                elif cmd == "/stats":
                    self._show_stats()
                elif cmd == "/resources":
                    self._show_resources()
                elif cmd == "/settings":
                    self._show_settings()
                elif cmd == "/clear":
                    self._clear_conversation()
                elif cmd == "/code":
                    self._toggle_code_execution()
                elif cmd == "/rag":
                    self._toggle_rag()
                elif cmd == "/dummy":
                    self._toggle_dummy_tools()
                else:
                    print(f"Unknown command: {user_input}")
                    print("Type /help for available commands")
                continue

            # Process query
            try:
                response = self._assistant.query(user_input)
                if response:
                    print(f"\nAssistant: {response}")
                else:
                    print(
                        "\nAssistant: I couldn't generate a response. Please try rephrasing your question."
                    )
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
        while True:
            if interactive:
                should_continue = self.show_settings_menu()
                if not should_continue:
                    print("Goodbye!")
                    return

            try:
                return_to_menu = self.run_assistant()
                if return_to_menu:
                    # User requested to return to menu
                    interactive = True
                    continue
                else:
                    # User quit
                    return
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
  python -m src.mcp.client --no-menu --code-execution  # Code execution mode
  python -m src.mcp.client -i --code-execution   # Menu with code exec enabled
        """,
    )
    parser.add_argument(
        "--code-execution",
        action="store_true",
        default=False,
        dest="code_execution",
        help="Enable code execution mode (default: disabled)",
    )
    parser.add_argument(
        "--no-code-execution",
        action="store_false",
        dest="code_execution",
        help="Disable code execution (use traditional JSON tools, this is the default)",
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
    # Check if --code-execution was explicitly passed (code_execution will be True)
    # or if any other feature flags were explicitly passed
    if args.code_execution:
        config.enable_code_execution = True
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
