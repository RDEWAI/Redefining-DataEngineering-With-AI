#!/usr/bin/env python3
"""PostToolUse hook: remind agent of pending learnings after Write/Edit."""

import json
import os
import sys

ROLE = "developer"
OUTPUT_PATH_MARKERS = (
    "/patient_360/",
    "/airflow/dags/",
    "/_infra/ci/",
)


def main():
    try:
        input_data = json.load(sys.stdin)
    except (json.JSONDecodeError, EOFError):
        sys.exit(0)

    tool_input = input_data.get("tool_input", {})
    file_path = tool_input.get("file_path", "")

    if not any(marker in file_path for marker in OUTPUT_PATH_MARKERS):
        sys.exit(0)

    # chapter-5/developer-plugin/scripts/ → chapter-5/
    chapter_root = os.path.dirname(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    )
    queue_file = os.path.join(chapter_root, "memory", ROLE, "learnings-queue.jsonl")

    if not os.path.exists(queue_file):
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
        output = {
            "hookSpecificOutput": {
                "hookEventName": "PostToolUse",
                "additionalContext": (
                    f"LEARNINGS QUEUE: {pending_count} pending correction(s) in "
                    f"memory/{ROLE}/learnings-queue.jsonl. "
                    f"Run /developer-plugin:apply-learnings after completing the current skill."
                ),
            }
        }
        print(json.dumps(output))

    sys.exit(0)


if __name__ == "__main__":
    main()
