#!/usr/bin/env bash
# Shared fixture builder for developer-plugin eval cases.
#
# Builds a slim copy of the chapter workspace (outputs/, inputs/code/, the
# patient_360 project minus runtime data) into the eval sandbox working
# directory so that the plugin's workspace discovery
# (skills/validate-stories/scripts/status_rollup.py --mode discover) resolves
# exactly as it does in the real chapter.
#
# Runs OUTSIDE the eval sandbox, as the invoking user, only when the runner is
# given --scaffold. Never copies uc-warehouse/ (tens of GB) or runtime secrets.
#
# Usage (from a case's scaffold.sh):
#   bash "$(dirname "$0")/../scaffold/build_workspace.sh" [--defect NAME] [--drop-dag] [--dest DIR]
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CHAPTER_ROOT="$(cd "$HERE/../../.." && pwd)"   # evals/scaffold -> developer-plugin -> chapter-N
DEST="$PWD"
DEFECTS=()
DROP_DAG=0

while [ $# -gt 0 ]; do
  case "$1" in
    --defect) DEFECTS+=("$2"); shift 2 ;;
    --drop-dag) DROP_DAG=1; shift ;;
    --dest) DEST="$2"; shift 2 ;;
    *) echo "build_workspace.sh: unknown arg $1" >&2; exit 2 ;;
  esac
done

for must in outputs inputs/code pyproject.toml uv.lock patient_360/pyproject.toml patient_360/src; do
  [ -e "$CHAPTER_ROOT/$must" ] || { echo "build_workspace.sh: missing $CHAPTER_ROOT/$must" >&2; exit 2; }
done

mkdir -p "$DEST"
EXCL=(--exclude '__pycache__/' --exclude '.venv/' --exclude '*.egg-info' --exclude '.skill-arg'
      --exclude '.skill-paths' --exclude 'token.txt' --exclude '*.bak' --exclude '.DS_Store')

# Workspace root files
rsync -a "${EXCL[@]}" "$CHAPTER_ROOT/pyproject.toml" "$CHAPTER_ROOT/uv.lock" "$DEST/"
rsync -a "${EXCL[@]}" "$CHAPTER_ROOT/outputs/" "$DEST/outputs/"
mkdir -p "$DEST/inputs"
rsync -a "${EXCL[@]}" "$CHAPTER_ROOT/inputs/code/" "$DEST/inputs/code/"

# Project: explicit allow-list, never the whole tree
P="$CHAPTER_ROOT/patient_360"
mkdir -p "$DEST/patient_360/_infra/docker"
for item in pyproject.toml uv.lock Makefile README.md CLAUDE.md src airflow contracts dq_rules ddl tests; do
  [ -e "$P/$item" ] && rsync -a "${EXCL[@]}" --exclude 'uc-warehouse/' "$P/$item" "$DEST/patient_360/"
done
[ -f "$P/_infra/docker/docker-compose.yml" ] && cp "$P/_infra/docker/docker-compose.yml" "$DEST/patient_360/_infra/docker/"

# Make `uv run python` resolve in the sandbox (workspace deps are light: jinja2, pyyaml, openpyxl).
( cd "$DEST" && uv sync --frozen --quiet )

if [ "$DROP_DAG" = 1 ]; then
  rm -f "$DEST"/patient_360/airflow/dags/*.py
  touch "$DEST/patient_360/airflow/dags/__init__.py"
fi

for d in "${DEFECTS[@]:-}"; do
  [ -z "$d" ] && continue
  f="$HERE/defects/$d.sh"
  [ -f "$f" ] || { echo "build_workspace.sh: no defect script $f" >&2; exit 2; }
  DEST="$DEST" bash "$f"
done

echo "fixture ready at $DEST ($(du -sh "$DEST" | cut -f1))"
