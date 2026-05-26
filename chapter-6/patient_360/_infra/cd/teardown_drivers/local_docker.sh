#!/usr/bin/env bash
# local-docker teardown driver for the pr-process skill.
#
# Implements the driver contract documented in:
#   inputs/code/v1/teardown-pattern.md
#   developer-plugin/skills/pr-process/scripts/teardown_drivers/README.md
#
# Modes (positional argument 1):
#   --check    : print JSON summary of what *would* be destroyed; exit 0.
#   --dry-run  : print the exact shell commands; exit 0.
#   --destroy  : actually destroy; print JSON summary on success; exit 0.
#
# The driver scopes everything to the docker-compose project at
# {project_root}/_infra/docker/docker-compose.yml — it never runs
# `docker system prune` or unfiltered `docker volume prune`.

set -euo pipefail

MODE="${1:-}"
if [[ -z "$MODE" ]]; then
  echo "usage: $0 --check | --dry-run | --destroy" >&2
  exit 64
fi

# Resolve project root: prefer $PATIENT360_PROJECT_ROOT, else walk up from $PWD
# looking for _infra/docker/docker-compose.yml.
resolve_project_root() {
  if [[ -n "${PATIENT360_PROJECT_ROOT:-}" && -f "${PATIENT360_PROJECT_ROOT}/_infra/docker/docker-compose.yml" ]]; then
    echo "$PATIENT360_PROJECT_ROOT"
    return
  fi
  local dir="$PWD"
  while [[ "$dir" != "/" ]]; do
    if [[ -f "$dir/_infra/docker/docker-compose.yml" ]]; then
      echo "$dir"
      return
    fi
    dir="$(dirname "$dir")"
  done
  echo "" # not found
}

PROJECT_ROOT="$(resolve_project_root)"
if [[ -z "$PROJECT_ROOT" ]]; then
  cat >&2 <<EOF
{"driver":"local-docker","error":"could not locate docker-compose.yml. Set PATIENT360_PROJECT_ROOT or run from inside the project."}
EOF
  exit 65
fi

COMPOSE_FILE="$PROJECT_ROOT/_infra/docker/docker-compose.yml"
# Pin the compose project name so it matches what the JSON summary
# claims. Without `-p $PROJECT_NAME` on every `docker compose` call,
# compose would default to `basename(dirname(compose-file))` (e.g.
# `docker`), so volume names like `${PROJECT_NAME}_uc-data` wouldn't
# match Docker's actual `docker_uc-data` — the destroy would target
# the wrong project.
PROJECT_NAME="$(basename "$PROJECT_ROOT")"
COMPOSE=(docker compose -f "$COMPOSE_FILE" -p "$PROJECT_NAME")
UC_SOURCE_DIR="$PROJECT_ROOT/_infra/docker/uc-source"
UC_SOURCE_MARKER="$PROJECT_ROOT/_infra/docker/.uc-ui-source"

started_at="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

# What we plan to destroy (used by --check and the final --destroy summary).
plan_json() {
  local destroyed='[]'
  local skipped='[]'
  destroyed=$(cat <<JSON
[
  {"kind":"compose-project","name":"$PROJECT_NAME"},
  {"kind":"volume","name":"${PROJECT_NAME}_uc-data"},
  {"kind":"volume","name":"${PROJECT_NAME}_marquez-db"},
  {"kind":"network","name":"${PROJECT_NAME}_default"}
]
JSON
)
  if [[ -d "$UC_SOURCE_DIR" && -f "$UC_SOURCE_MARKER" ]]; then
    # Env-var prefix MUST come BEFORE the `python3` invocation, not
    # after the heredoc terminator. The previous version placed the
    # assignments after `PY`, where they ran as a separate no-op
    # statement and `os.environ["DESTROYED_JSON"]` raised KeyError.
    destroyed=$(DESTROYED_JSON="$destroyed" UC_SOURCE_DIR="$UC_SOURCE_DIR" python3 - <<'PY'
import json, os
d = json.loads(os.environ["DESTROYED_JSON"])
d.append({"kind": "directory", "name": os.environ["UC_SOURCE_DIR"]})
print(json.dumps(d))
PY
)
  fi
  cat <<JSON
{
  "driver": "local-docker",
  "started_at": "$started_at",
  "project_root": "$PROJECT_ROOT",
  "compose_file": "$COMPOSE_FILE",
  "destroyed": $destroyed,
  "skipped": $skipped
}
JSON
}

dry_run_commands() {
  cat <<EOF
docker compose -f "$COMPOSE_FILE" -p "$PROJECT_NAME" down -v --remove-orphans
docker volume prune -f --filter "label=project=$PROJECT_NAME"
EOF
  if [[ -d "$UC_SOURCE_DIR" && -f "$UC_SOURCE_MARKER" ]]; then
    echo "rm -rf \"$UC_SOURCE_DIR\""
  fi
}

case "$MODE" in
  --check)
    plan_json
    exit 0
    ;;
  --dry-run)
    dry_run_commands
    exit 0
    ;;
  --destroy)
    start_ts=$(date +%s)

    if ! command -v docker >/dev/null 2>&1; then
      echo '{"driver":"local-docker","error":"docker CLI not installed"}' >&2
      exit 66
    fi

    # Step 1: compose down -v --remove-orphans (removes named volumes too).
    # Capture stderr from the FIRST run — running it twice (the previous
    # version's pattern) would let a partial first cleanup mask the real
    # error from the second invocation, producing `{"detail":""}` exit 1
    # on a system that's actually been torn down.
    err=$("${COMPOSE[@]}" down -v --remove-orphans 2>&1)
    rc=$?
    if [[ $rc -ne 0 ]]; then
      cat >&2 <<EOF
{"driver":"local-docker","error":"docker compose down failed","detail":$(printf '%s' "$err" | python3 -c 'import json,sys;print(json.dumps(sys.stdin.read()))')}
EOF
      exit 1
    fi

    # Step 2: prune project-labelled stragglers (scoped by label filter).
    docker volume prune -f --filter "label=project=$PROJECT_NAME" >/dev/null 2>&1 || true

    # Step 3: optionally remove the UC-UI source clone if the marker exists.
    if [[ -d "$UC_SOURCE_DIR" && -f "$UC_SOURCE_MARKER" ]]; then
      rm -rf "$UC_SOURCE_DIR"
    fi

    end_ts=$(date +%s)
    duration=$((end_ts - start_ts))

    plan_json | python3 - "$duration" <<'PY'
import json, sys
data = json.loads(sys.stdin.read())
data["duration_s"] = int(sys.argv[1])
print(json.dumps(data, indent=2))
PY
    exit 0
    ;;
  *)
    echo "unknown mode: $MODE (expected --check | --dry-run | --destroy)" >&2
    exit 64
    ;;
esac
