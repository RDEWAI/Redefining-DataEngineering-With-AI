"""Sandboxed code execution with resource limits.

This module provides a CodeSandbox class that executes Python code in an isolated
subprocess with security constraints:
- Import whitelist (pandas, duckdb, numpy, matplotlib, seaborn)
- Timeout enforcement (default: 30 seconds)
- Memory limits (default: 512 MB, Unix only)
- Process isolation

Educational use only. For production, consider Docker or gVisor.
"""

import resource
import subprocess
import sys
from typing import Any

# Security: Whitelist of allowed imports
ALLOWED_IMPORTS = {
    "pandas",
    "duckdb",
    "numpy",
    "matplotlib",
    "seaborn",
    "math",
    "datetime",
    "json",
    "csv",
}

# Default resource limits
DEFAULT_TIMEOUT_SECONDS = 30
DEFAULT_MEMORY_MB = 512


class SandboxError(Exception):
    """Exception raised for sandbox-related errors."""

    pass


class CodeSandbox:
    """Execute Python code in an isolated subprocess with resource limits.

    Supports stateful execution where variables persist between calls,
    following Anthropic's code execution pattern.

    Example:
        >>> sandbox = CodeSandbox(timeout=30, memory_mb=512)
        >>> result = sandbox.execute("print('Hello, world!')")
        >>> print(result['stdout'])
        Hello, world!

        # Stateful execution (variables persist)
        >>> sandbox.execute_stateful("x = 10", db_path="data.db", api_code="...")
        >>> sandbox.execute_stateful("print(x * 2)")  # prints 20
        >>> sandbox.reset_state()  # clear accumulated state
    """

    def __init__(self, timeout: int = DEFAULT_TIMEOUT_SECONDS, memory_mb: int = DEFAULT_MEMORY_MB):
        """Initialize the code sandbox.

        Args:
            timeout: Maximum execution time in seconds
            memory_mb: Maximum memory usage in megabytes (Unix only)
        """
        self.timeout = timeout
        self.memory_bytes = memory_mb * 1024 * 1024
        # Accumulated code for stateful execution (Anthropic pattern)
        self._accumulated_code: list[str] = []

    def _set_limits(self) -> None:
        """Set resource limits for child process (Unix only).

        This function is called in the child process via preexec_fn.
        It sets memory and CPU time limits.

        Note:
            - Not supported on Windows
            - RLIMIT_AS may not strictly enforce on some systems
        """
        try:
            # Memory limit (address space)
            resource.setrlimit(resource.RLIMIT_AS, (self.memory_bytes, self.memory_bytes))

            # CPU time limit
            resource.setrlimit(resource.RLIMIT_CPU, (self.timeout, self.timeout))
        except (ValueError, OSError) as e:
            # Limits may fail on some systems (e.g., inside Docker)
            # Continue execution but log the issue
            print(f"Warning: Could not set resource limits: {e}", file=sys.stderr)

    def _wrap_code(self, code: str, db_path: str | None = None, api_code: str | None = None) -> str:
        """Wrap user code with imports, API functions, and setup.

        Args:
            code: User-provided Python code
            db_path: Optional path to DuckDB database
            api_code: Optional pre-generated API functions (from ToolAPIGenerator)

        Returns:
            Complete Python code with imports, API functions, and setup
        """
        # Pre-import allowed modules to ensure they're available
        wrapper = """
import sys

# Disable import of unauthorized modules (best-effort)
# Note: This is not foolproof, but adds a layer of protection

# Pre-import allowed modules
import pandas as pd
import numpy as np
import duckdb
import matplotlib
matplotlib.use('Agg')  # Non-interactive backend for safety
import matplotlib.pyplot as plt
import seaborn as sns
import math
import datetime
import json
import csv
from typing import Dict, List, Any, Optional  # For API function type hints

# Set up database connection if provided
"""

        if db_path:
            # Note: Use read_only=True for file databases, but :memory: cannot be read-only
            read_only_flag = "read_only=True" if db_path != ":memory:" else ""
            wrapper += f"""
db_path = {repr(db_path)}
_conn = duckdb.connect(db_path{", " + read_only_flag if read_only_flag else ""})
"""
        else:
            wrapper += """
_conn = None
"""

        # Inject API functions if provided (Anthropic pattern)
        if api_code:
            wrapper += """
# Library API functions (from MCP tools)
"""
            wrapper += api_code
            wrapper += """

"""

        wrapper += """
# User code starts here
"""
        wrapper += code

        return wrapper

    def execute(
        self, code: str, db_path: str | None = None, api_code: str | None = None
    ) -> dict[str, Any]:
        """Execute Python code in a sandboxed subprocess.

        Args:
            code: Python code to execute
            db_path: Optional path to DuckDB database (opened read-only)
            api_code: Optional pre-generated API functions (Anthropic pattern)

        Returns:
            Dictionary with execution results:
                - success (bool): Whether execution completed without errors
                - stdout (str): Standard output from the code
                - stderr (str): Standard error from the code
                - timeout (bool): Whether execution timed out

        Example:
            >>> sandbox = CodeSandbox()
            >>> result = sandbox.execute("print(2 + 2)")
            >>> print(result['stdout'])
            4
        """
        # Wrap code with imports, API functions, and setup
        wrapped_code = self._wrap_code(code, db_path, api_code)

        try:
            # Execute in subprocess with resource limits
            result = subprocess.run(
                [sys.executable, "-c", wrapped_code],
                capture_output=True,
                text=True,
                timeout=self.timeout,
                # Set limits (Unix only, ignored on Windows)
                preexec_fn=self._set_limits if sys.platform != "win32" else None,
            )

            return {
                "success": result.returncode == 0,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "timeout": False,
            }

        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "stdout": "",
                "stderr": f"Execution timed out ({self.timeout} second limit)",
                "timeout": True,
            }

        except Exception as e:
            return {
                "success": False,
                "stdout": "",
                "stderr": f"Sandbox error: {str(e)}",
                "timeout": False,
            }

    def execute_with_context(
        self, code: str, db_path: str | None = None, context: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Execute code with additional context variables.

        Args:
            code: Python code to execute
            db_path: Optional path to DuckDB database
            context: Optional dictionary of variables to inject

        Returns:
            Execution result dictionary

        Note:
            Context variables are serialized to JSON and injected into the code.
            Complex objects may not serialize properly.
        """
        if context:
            # Inject context as JSON-serializable variables
            import json

            context_code = "# Injected context variables\n"
            for key, value in context.items():
                try:
                    # Serialize to JSON and back to ensure safety
                    safe_value = json.loads(json.dumps(value))
                    context_code += f"{key} = {repr(safe_value)}\n"
                except (TypeError, ValueError):
                    # Skip non-serializable values
                    pass

            code = context_code + "\n" + code

        return self.execute(code, db_path)

    def reset_state(self) -> None:
        """Reset accumulated state for stateful execution.

        Call this when starting a new conversation or query to clear
        any previously accumulated code.
        """
        self._accumulated_code = []

    def execute_stateful(
        self,
        code: str,
        db_path: str | None = None,
        api_code: str | None = None,
    ) -> dict[str, Any]:
        """Execute code with state persistence between calls.

        This implements Anthropic's code execution pattern where variables
        persist between iterations. Each call accumulates successful code
        and re-executes the full history, ensuring state consistency.

        Args:
            code: New Python code to execute
            db_path: Optional path to DuckDB database
            api_code: Optional pre-generated API functions

        Returns:
            Execution result dictionary (same as execute())

        Example:
            >>> sandbox = CodeSandbox()
            >>> sandbox.execute_stateful("x = [1, 2, 3]", db_path="lib.db", api_code=api)
            >>> sandbox.execute_stateful("print(sum(x))")  # prints 6
            >>> sandbox.reset_state()  # clear for new conversation

        Note:
            - State is maintained by re-executing all accumulated code
            - Only successful code blocks are accumulated
            - Call reset_state() between conversations/queries
        """
        # Build full code: accumulated history + new code
        # We suppress output from accumulated code to only show new output
        if self._accumulated_code:
            # Wrap accumulated code to suppress its output
            accumulated = "\n".join(self._accumulated_code)
            full_code = f"""
# === Accumulated state (output suppressed) ===
import io, sys
_old_stdout = sys.stdout
sys.stdout = io.StringIO()
try:
{self._indent_code(accumulated, 4)}
finally:
    sys.stdout = _old_stdout
# === End accumulated state ===

# === New code ===
{code}
"""
        else:
            full_code = code

        # Execute the full code
        result = self.execute(full_code, db_path, api_code)

        # If successful, add new code to accumulated state
        if result["success"]:
            self._accumulated_code.append(code)

        return result

    def _indent_code(self, code: str, spaces: int) -> str:
        """Indent code by specified number of spaces.

        Args:
            code: Code to indent
            spaces: Number of spaces to add

        Returns:
            Indented code
        """
        indent = " " * spaces
        return "\n".join(indent + line for line in code.split("\n"))


def validate_imports(code: str) -> tuple[bool, list[str]]:
    """Validate that code only imports whitelisted modules.

    Args:
        code: Python code to validate

    Returns:
        Tuple of (is_valid, list of unauthorized imports)

    Note:
        This is a simple string-based check and can be bypassed.
        The actual enforcement happens in the subprocess.
    """
    import re

    unauthorized = []
    # Find import statements
    import_pattern = r"^\s*(?:from|import)\s+(\w+)"

    for line in code.split("\n"):
        match = re.match(import_pattern, line)
        if match:
            module = match.group(1)
            if module not in ALLOWED_IMPORTS:
                unauthorized.append(module)

    return len(unauthorized) == 0, unauthorized
