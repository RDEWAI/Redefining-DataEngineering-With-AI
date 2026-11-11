#!/usr/bin/env bash
set -euo pipefail
bash "$(dirname "${BASH_SOURCE[0]}")/../scaffold/build_workspace.sh" --defect dag-relative-path
