#!/usr/bin/env python3
"""PostToolUse hook: remind agent of pending learnings after Write/Edit.

Project-agnostic: the hook discovers the workspace via the sibling
``discover_workspace.py`` helper starting from the edited file's directory, then
reads the learnings queue at ``{workspace_root}/memory/sre/``. If the
edit is outside any discoverable workspace, the hook fails open and exits 0.
"""

import importlib.util
import json
import sys
from pathlib import Path

ROLE = "sre"


def _load_discovery_module():
    here = Path(__file__).resolve()
    helper = here.parent / "discover_workspace.py"
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


def main():
    try:
        input_data = json.load(sys.stdin)
    except (json.JSONDecodeError, EOFError):
        sys.exit(0)

    tool_input = input_data.get("tool_input", {})
    file_path = tool_input.get("file_path", "")
    if not file_path:
        sys.exit(0)

    rollup = _load_discovery_module()
    if rollup is None:
        sys.exit(0)

    start = Path(file_path).parent
    try:
        ws = rollup.discover_workspace(start=start)
    except Exception:
        sys.exit(0)

    # Only remind when the edit is inside the discovered project. Edits
    # outside the project tree (docs, other chapters) should not trigger.
    try:
        Path(file_path).resolve().relative_to(ws.project_root)
    except ValueError:
        sys.exit(0)

    queue_file = ws.learnings_queue
    if not queue_file.exists():
        sys.exit(0)

    pending_count = 0
    try:
        with open(queue_file) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                    if entry.get("status") == "pending":
                        pending_count += 1
                except json.JSONDecodeError:
                    continue
    except OSError:
        sys.exit(0)

    if pending_count > 0:
        try:
            queue_display = queue_file.relative_to(ws.workspace_root).as_posix()
        except ValueError:
            queue_display = str(queue_file)
        output = {
            "hookSpecificOutput": {
                "hookEventName": "PostToolUse",
                "additionalContext": (
                    f"LEARNINGS QUEUE: {pending_count} pending correction(s) in "
                    f"{queue_display}. "
                    f"Run the correction through the rca skill's Learnings & Corrections step."
                ),
            }
        }
        print(json.dumps(output))

    sys.exit(0)


if __name__ == "__main__":
    main()
