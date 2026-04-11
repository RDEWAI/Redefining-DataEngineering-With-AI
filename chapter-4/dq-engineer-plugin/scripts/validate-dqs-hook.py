#!/usr/bin/env python3
"""PostToolUse hook: auto-validate DQS files and generate SE YAML rules.

After Write/Edit to outputs/dqs/*.md:
1. Validate DQS markdown (existing behavior)
2. If no CRITICAL issues, auto-generate per-table SE YAML files
3. Validate each generated YAML against SE's loading rules
4. Report all results via additionalContext
"""

import glob
import json
import os
import subprocess
import sys


def _find_chapter_root(file_path: str) -> str:
    """Walk up from file_path to find the chapter-4 root directory.

    Looks for the directory containing dq-engineer-plugin/.
    """
    current = os.path.dirname(os.path.abspath(file_path))
    for _ in range(10):  # safety limit
        if os.path.isdir(os.path.join(current, "dq-engineer-plugin")):
            return current
        parent = os.path.dirname(current)
        if parent == current:
            break
        current = parent
    # Fallback: derive from plugin_root
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _generate_se_rules(file_path: str, plugin_root: str, context_parts: list[str]) -> None:
    """Generate and validate SE YAML files from a DQS markdown file.

    Appends status messages to context_parts (list of strings).
    Never raises — all errors are captured as warnings.
    """
    generator = os.path.join(
        plugin_root, "skills", "generate-se-rules", "scripts", "generate_se_rules.py"
    )
    if not os.path.exists(generator):
        return

    # Discover paths
    version_dir = os.path.dirname(file_path)  # e.g., .../outputs/dqs/v1/
    version_name = os.path.basename(version_dir)  # e.g., "v1"
    chapter_root = _find_chapter_root(file_path)
    se_config = os.path.join(chapter_root, "inputs", "dqs", version_name, "se-config-template.yaml")
    se_output_dir = os.path.join(version_dir, "se-rules")

    # Build CLI args — config is optional
    cmd = [sys.executable, generator, file_path, "-o", se_output_dir]
    if os.path.exists(se_config):
        cmd.extend(["--config", se_config])

    # Run generator
    try:
        gen_result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    except (subprocess.TimeoutExpired, OSError) as exc:
        context_parts.append(f"SE generation skipped: {exc}")
        return

    if gen_result.returncode != 0:
        context_parts.append(
            f"SE generation failed (exit {gen_result.returncode}): {gen_result.stderr.strip()}"
        )
        return

    # Count generated files
    yaml_files = glob.glob(os.path.join(se_output_dir, "se-rules-*.yaml"))
    if not yaml_files:
        context_parts.append("SE generation produced no YAML files.")
        return

    context_parts.append(f"SE YAML generated: {len(yaml_files)} file(s) in {se_output_dir}/")

    # Validate each generated YAML using the SE validator port
    gen_scripts_dir = os.path.join(plugin_root, "skills", "generate-se-rules", "scripts")
    try:
        sys.path.insert(0, gen_scripts_dir)
        from generate_se_rules import validate_se_yaml  # noqa: E402
    except ImportError:
        context_parts.append("SE validation skipped: cannot import validate_se_yaml")
        return
    finally:
        if gen_scripts_dir in sys.path:
            sys.path.remove(gen_scripts_dir)

    se_errors: list[str] = []
    for yaml_file in yaml_files:
        try:
            with open(yaml_file, encoding="utf-8") as fh:
                errors = validate_se_yaml(fh.read())
            if errors:
                basename = os.path.basename(yaml_file)
                for err in errors:
                    se_errors.append(f"  {basename}: {err}")
        except (OSError, Exception) as exc:  # noqa: BLE001
            se_errors.append(f"  {os.path.basename(yaml_file)}: read error: {exc}")

    if se_errors:
        context_parts.append("SE validation warnings:\n" + "\n".join(se_errors))
    else:
        context_parts.append("SE validation: all files passed.")


def main() -> None:
    try:
        input_data = json.load(sys.stdin)
    except (json.JSONDecodeError, EOFError):
        sys.exit(0)

    tool_input = input_data.get("tool_input", {})
    file_path = tool_input.get("file_path", "")

    # Only validate .md files in outputs/dqs/ — skip .yaml SE rules
    if "/outputs/dqs/" not in file_path or not file_path.endswith(".md"):
        sys.exit(0)

    plugin_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    validator = os.path.join(plugin_root, "skills", "validate-dqs", "scripts", "validate_dqs.py")

    if not os.path.exists(validator):
        sys.exit(0)

    try:
        result = subprocess.run(
            [sys.executable, validator, file_path],
            capture_output=True,
            text=True,
            timeout=25,
        )
    except (subprocess.TimeoutExpired, OSError):
        sys.exit(0)

    if result.returncode == 1:
        # CRITICAL issues — exit 2 blocks and feeds stderr back to Claude
        # Do NOT generate SE rules when DQS has critical issues
        print(result.stdout, file=sys.stderr)
        sys.exit(2)

    # Validation passed (0) or warnings only (2) — generate SE YAML
    context_parts: list[str] = []

    if result.returncode == 2:
        context_parts.append(
            f"DQS validation warnings for {os.path.basename(file_path)}:\n{result.stdout}"
        )

    # Auto-generate SE YAML rules from the DQS
    _generate_se_rules(file_path, plugin_root, context_parts)

    # Report everything via additionalContext
    if context_parts:
        output = {
            "hookSpecificOutput": {
                "hookEventName": "PostToolUse",
                "additionalContext": "\n".join(context_parts),
            }
        }
        print(json.dumps(output))

    sys.exit(0)


if __name__ == "__main__":
    main()
