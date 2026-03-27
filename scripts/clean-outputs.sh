#!/usr/bin/env bash
# Clean generated outputs and session memory for chapter-3 and chapter-4.
# Keeps DRD outputs in chapter-4 (used as input for the artifact chain).
# Keeps .gitkeep files and directory structure intact.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"

echo "=== Cleaning Chapter 3 ==="

# Chapter 3: outputs/drd/ (DRD files only)
echo "  Removing chapter-3 DRD outputs..."
find "$REPO_ROOT/chapter-3/outputs" -type f ! -name '.gitkeep' -delete 2>/dev/null || true

# Chapter 3: ba-plugin/memory/ (session notes)
echo "  Removing chapter-3 ba-plugin memory..."
find "$REPO_ROOT/chapter-3/ba-plugin/memory" -type f ! -name '.gitkeep' -delete 2>/dev/null || true

echo "=== Cleaning Chapter 4 ==="

# Chapter 4: outputs (everything EXCEPT drd/)
for artifact in hld dms stm dqs lld stories; do
  dir="$REPO_ROOT/chapter-4/outputs/$artifact"
  if [ -d "$dir" ]; then
    echo "  Removing chapter-4 outputs/$artifact/..."
    find "$dir" -type f ! -name '.gitkeep' -delete 2>/dev/null || true
    # Remove any subdirectories (e.g., stories/v1/EPIC-01-*/, dqs/v1/se-rules/)
    find "$dir" -mindepth 2 -type d -empty -delete 2>/dev/null || true
  fi
done

# Chapter 4: session memory and learnings
echo "  Removing chapter-4 memory (session notes + learnings)..."
find "$REPO_ROOT/chapter-4/memory" -type f \( -name 'session-*.md' -o -name 'learnings-queue.jsonl' \) -delete 2>/dev/null || true

echo ""
echo "Done. Preserved:"
echo "  - chapter-4/outputs/drd/v1/ (DRD from Chapter 3 — input for the chain)"
echo "  - All inputs/ directories (seed documents)"
echo "  - All .gitkeep files and directory structure"
