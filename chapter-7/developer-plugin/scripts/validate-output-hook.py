#!/usr/bin/env python3
"""PostToolUse hook: auto-validate developer outputs after Write/Edit.

Detects which artifact type was written and invokes the appropriate
validate-* skill script. The hook is project-agnostic: it discovers the
workspace via the sibling ``status_rollup.py`` helper (walking upward from
the edited file), then checks whether the file lives under the discovered
project's Bronze source tree or Airflow configs directory before dispatching
the validator.

Validation errors at CRITICAL level block the tool response (exit 2);
warnings are surfaced as additional context. The hook always fails open on
discovery errors or missing tooling so a broken plugin install never blocks
user edits.
"""

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path


def _load_discovery_module():
    """Import ``status_rollup`` from the sibling validate-stories skill."""
    here = Path(__file__).resolve()
    helper = here.parent.parent / "skills" / "validate-stories" / "scripts" / "status_rollup.py"
    if not helper.exists():
        return None
    module_name = "_rdewai_status_rollup"
    if module_name in sys.modules:
        return sys.modules[module_name]
    spec = importlib.util.spec_from_file_location(module_name, helper)
    if spec is None or spec.loader is None:
        return None
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    try:
        spec.loader.exec_module(module)
    except Exception:
        sys.modules.pop(module_name, None)
        return None
    return module


def _skill_validate(validator_path: str, args: list[str]) -> None:
    if not os.path.exists(validator_path):
        sys.exit(0)

    try:
        result = subprocess.run(
            [sys.executable, validator_path] + args,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (subprocess.TimeoutExpired, OSError):
        sys.exit(0)

    if result.returncode == 1:
        print(result.stdout, file=sys.stderr)
        sys.exit(2)
    elif result.returncode == 2:
        output = {
            "hookSpecificOutput": {
                "hookEventName": "PostToolUse",
                "additionalContext": result.stdout,
            }
        }
        print(json.dumps(output))
    sys.exit(0)


def main():
    try:
        input_data = json.load(sys.stdin)
    except (json.JSONDecodeError, EOFError):
        sys.exit(0)

    tool_input = input_data.get("tool_input", {})
    file_path = tool_input.get("file_path", "")

    if not file_path:
        sys.exit(0)
    if not (file_path.endswith(".py") or file_path.endswith(".yml")):
        sys.exit(0)

    # Only interested in ingestion-shaped paths. Cheap filename prefilter
    # before incurring discovery cost — skips most Write/Edit calls.
    if "/bronze/" not in file_path and "/airflow/configs/" not in file_path:
        sys.exit(0)

    rollup = _load_discovery_module()
    if rollup is None:
        sys.exit(0)

    # Discovery walk-up starts at the file's directory (CWD may be anywhere).
    # If discovery fails, the edit isn't inside a plugin-managed workspace —
    # fail open.
    start = Path(file_path).parent
    try:
        ws = rollup.discover_workspace(start=start)
    except Exception:
        sys.exit(0)

    project_root = ws.project_root
    project_name = ws.project_name

    try:
        rel = Path(file_path).resolve().relative_to(project_root)
    except ValueError:
        # File is outside the discovered project (e.g. upstream artifact content)
        sys.exit(0)

    rel_posix = rel.as_posix()
    is_bronze_module = rel_posix.startswith(f"src/{project_name}/bronze/") and rel_posix.endswith(
        ".py"
    )
    is_airflow_config = rel_posix.startswith("airflow/configs/") and rel_posix.endswith(
        (".yml", ".yaml")
    )

    if not (is_bronze_module or is_airflow_config):
        sys.exit(0)

    plugin_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    validator = os.path.join(
        plugin_root,
        "skills",
        "validate-ingestion",
        "scripts",
        "validate_ingestion.py",
    )
    _skill_validate(
        validator,
        [
            "--project-root",
            str(project_root),
            "--project-name",
            project_name,
            "--workspace-root",
            str(ws.workspace_root),
        ],
    )


if __name__ == "__main__":
    main()
