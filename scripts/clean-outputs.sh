#!/usr/bin/env bash
# Clean generated outputs and session memory for chapter-3 and chapter-4.
# After cleaning, copies chapter-3 DRD outputs into chapter-4 as unapproved
# starting points (users must run approve-drd before creating downstream artifacts).
# Keeps .gitkeep files and directory structure intact.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"

echo "=== Cleaning Chapter 4 ==="

# Chapter 4: outputs (ALL artifacts including drd/)
for artifact in drd hld dms stm dqs lld stories; do
  dir="$REPO_ROOT/chapter-4/outputs/$artifact"
  if [ -d "$dir" ]; then
    echo "  Removing chapter-4 outputs/$artifact/..."
    find "$dir" -type f ! -name '.gitkeep' -delete 2>/dev/null || true
    # Remove any subdirectories (e.g., stories/v1/EPIC-01-*/, dqs/v1/se-rules/)
    find "$dir" -mindepth 2 -type d -empty -delete 2>/dev/null || true
  fi
done

# Copy chapter-3 DRD outputs into chapter-4/outputs/drd/v1/ (exact copy)
# Must happen BEFORE chapter-3 cleanup so source files still exist
echo "  Copying chapter-3 DRD outputs → chapter-4/outputs/drd/v1/..."
mkdir -p "$REPO_ROOT/chapter-4/outputs/drd/v1"
for src in "$REPO_ROOT/chapter-3/outputs/drd"/DRD-*.md; do
  [ -f "$src" ] || continue
  cp "$src" "$REPO_ROOT/chapter-4/outputs/drd/v1/"
done

# Chapter 4: session memory and learnings
echo "  Removing chapter-4 memory (session notes + learnings)..."
find "$REPO_ROOT/chapter-4/memory" -type f \( -name 'session-*.md' -o -name 'learnings-queue.jsonl' \) -delete 2>/dev/null || true

echo "=== Cleaning Chapter 3 ==="

# Chapter 3: outputs/drd/ (DRD files only) — cleaned AFTER copy to chapter-4
echo "  Removing chapter-3 DRD outputs..."
find "$REPO_ROOT/chapter-3/outputs" -type f ! -name '.gitkeep' -delete 2>/dev/null || true

# Chapter 3: memory/ (session notes + learnings)
echo "  Removing chapter-3 memory (session notes + learnings)..."
find "$REPO_ROOT/chapter-3/memory" -type f \( -name 'session-*.md' -o -name 'learnings-queue.jsonl' \) -delete 2>/dev/null || true

echo ""
echo "Done. Actions:"
echo "  - Cleaned all chapter-3 and chapter-4 outputs"
echo "  - Copied chapter-3 DRD outputs → chapter-4/outputs/drd/v1/ (unapproved — run approve-drd to unlock HLD creation)"
echo "  - Preserved all inputs/ directories and .gitkeep files"
