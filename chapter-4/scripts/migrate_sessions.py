#!/usr/bin/env python3
"""Migrate existing sessions from inline to file-based artifact storage.

This script converts legacy session files (<session_id>.json) to the new
directory-based format:

OLD FORMAT:
.pwi/sessions/
├── abc12345.json     # Contains all artifact content inline

NEW FORMAT:
.pwi/sessions/
└── abc12345/
    ├── session.json  # Metadata only (no artifact content)
    ├── drd.md        # Data Requirements Document
    ├── pad.md        # Pipeline Architecture Document
    ├── dmd.csv       # Data Mapping Document
    ├── dqs.yaml      # Data Quality Specification
    ├── stories.md    # User Stories
    └── package.md    # Final Delivery Package

Usage:
    python scripts/migrate_sessions.py [--dry-run] [--session SESSION_ID]

Options:
    --dry-run      Show what would be done without making changes
    --session ID   Migrate only the specified session
"""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path


def get_artifact_extension(artifact_format: str) -> str:
    """Get file extension for artifact format."""
    extensions = {
        "markdown": ".md",
        "csv": ".csv",
        "yaml": ".yaml",
        "json": ".json",
    }
    return extensions.get(artifact_format, ".txt")


def migrate_session(
    old_json_path: Path,
    sessions_dir: Path,
    dry_run: bool = False,
) -> bool:
    """Migrate a single session from legacy to file-based format.

    Args:
        old_json_path: Path to the legacy session JSON file.
        sessions_dir: Base sessions directory.
        dry_run: If True, only show what would be done.

    Returns:
        True if migration successful, False otherwise.
    """
    try:
        # Load old session
        with open(old_json_path, encoding="utf-8") as f:
            old_session = json.load(f)

        session_id = old_session.get("session_id", old_json_path.stem)
        session_dir = sessions_dir / session_id

        print(f"\nMigrating session: {session_id}")
        print(f"  Source: {old_json_path}")
        print(f"  Target: {session_dir}/")

        if session_dir.exists():
            print(f"  WARNING: Session directory already exists, skipping")
            return False

        if dry_run:
            print("  [DRY RUN] Would create directory structure:")
        else:
            session_dir.mkdir(parents=True, exist_ok=True)

        # Process artifacts
        artifacts = old_session.get("artifacts", {})
        for artifact_type, artifact_data in artifacts.items():
            content = artifact_data.pop("content", "")
            artifact_format = artifact_data.get("format", "markdown")
            ext = get_artifact_extension(artifact_format)
            filename = f"{artifact_type}{ext}"
            artifact_data["filename"] = filename

            artifact_path = session_dir / filename

            if dry_run:
                content_preview = content[:50] + "..." if len(content) > 50 else content
                print(f"    - {filename}: {len(content)} chars ({content_preview})")
            else:
                artifact_path.write_text(content, encoding="utf-8")
                print(f"    - Created: {filename} ({len(content)} chars)")

        # Write session.json (without inline content)
        session_json_path = session_dir / "session.json"

        if dry_run:
            print(f"    - session.json (metadata only)")
        else:
            with open(session_json_path, "w", encoding="utf-8") as f:
                json.dump(old_session, f, indent=2)
            print(f"    - Created: session.json")

            # Backup and remove old file
            backup_path = old_json_path.with_suffix(".json.bak")
            shutil.copy(old_json_path, backup_path)
            old_json_path.unlink()
            print(f"    - Backed up and removed: {old_json_path.name}")

        return True

    except Exception as e:
        print(f"  ERROR: Failed to migrate: {e}")
        return False


def migrate_all_sessions(
    sessions_dir: Path,
    dry_run: bool = False,
    session_id: str | None = None,
) -> tuple[int, int]:
    """Migrate all legacy sessions to file-based format.

    Args:
        sessions_dir: Base sessions directory.
        dry_run: If True, only show what would be done.
        session_id: If provided, only migrate this session.

    Returns:
        Tuple of (successful_count, failed_count).
    """
    # Find legacy session files (*.json that are not inside directories)
    if session_id:
        legacy_files = [sessions_dir / f"{session_id}.json"]
        if not legacy_files[0].exists():
            print(f"Session not found: {session_id}")
            return (0, 1)
    else:
        legacy_files = [
            p for p in sessions_dir.glob("*.json")
            if p.is_file() and not (sessions_dir / p.stem).is_dir()
        ]

    if not legacy_files:
        print("No legacy session files found to migrate.")
        return (0, 0)

    print(f"Found {len(legacy_files)} legacy session(s) to migrate")
    if dry_run:
        print("[DRY RUN MODE - no changes will be made]")

    successful = 0
    failed = 0

    for json_path in legacy_files:
        if migrate_session(json_path, sessions_dir, dry_run):
            successful += 1
        else:
            failed += 1

    print(f"\n{'=' * 50}")
    print(f"Migration complete: {successful} successful, {failed} failed")

    return (successful, failed)


def main():
    parser = argparse.ArgumentParser(
        description="Migrate sessions from inline to file-based artifact storage"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without making changes",
    )
    parser.add_argument(
        "--session",
        type=str,
        help="Migrate only the specified session ID",
    )
    parser.add_argument(
        "--sessions-dir",
        type=Path,
        default=Path(".pwi/sessions"),
        help="Path to sessions directory (default: .pwi/sessions)",
    )

    args = parser.parse_args()

    if not args.sessions_dir.exists():
        print(f"Sessions directory not found: {args.sessions_dir}")
        return 1

    successful, failed = migrate_all_sessions(
        sessions_dir=args.sessions_dir,
        dry_run=args.dry_run,
        session_id=args.session,
    )

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    exit(main())
