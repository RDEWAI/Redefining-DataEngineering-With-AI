#!/usr/bin/env bash
# Build the chapter fixture workspace (reuses the developer-plugin builder), then
# drop the pre-collected evidence bundle for the alert under outputs/rca/v1/.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
bash "$HERE/../../../developer-plugin/evals/scaffold/build_workspace.sh"
ID=ALERT-20261014T153012Z-reconciliation_bronze
mkdir -p "$PWD/outputs/rca/v1/$ID" "$PWD/memory/sre"
cp -R "$HERE/../fixtures/se-missing/." "$PWD/outputs/rca/v1/$ID/"
touch "$PWD/memory/sre/learnings-queue.jsonl"
