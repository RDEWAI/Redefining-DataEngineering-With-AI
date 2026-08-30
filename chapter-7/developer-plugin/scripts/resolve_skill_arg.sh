#!/usr/bin/env bash
# Resolves a skill's target argument from the four canonical sources, in order:
#   1. $SKILL_ARG environment variable
#   2. <workspace>/.skill-arg file (consumed; deleted after read)
#   3. Conversational argument supplied as $1 (the user message)
#   4. $CLAUDE_AUTO_MODE=1 or <workspace>/.auto-mode marker -> "__AUTO__"
#
# Prints two lines on stdout:
#   <resolved_value>
#   <source: SKILL_ARG | .skill-arg | conversational | __AUTO__ | EMPTY>
#
# When the conversational arg contains one or more STORY-NN-NNN tokens, the
# whole comma-joined list is returned (preserves order, dedupes). Otherwise
# the first EPIC-NN, "Sprint N", or sync-* token is returned. Falls back to
# the trimmed input if no recognized token matches.
#
# Workspace resolution: if WORKSPACE_ROOT is unset, empty, the literal string
# "{workspace_root}" (placeholder didn't substitute), or points at a missing
# directory, the resolver walks up from $PWD looking for either
# `.claude-plugin/marketplace.json` or an `outputs/stories/v*/` directory --
# either marker uniquely identifies a chapter workspace. This makes the
# script robust to LLM callers that forgot to substitute the placeholder.
#
# Usage:
#   eval "$(WORKSPACE_ROOT=/path/to/chapter-5 \
#     bash resolve_skill_arg.sh "$USER_ARG" | \
#     awk 'NR==1{print "RESOLVED_ARG=\""$0"\""} NR==2{print "RESOLVED_SOURCE=\""$0"\""}')"
#
# Diagnostics are written to stderr when no source matched, listing every
# location that was probed so the caller (or LLM) can see exactly what was
# missing instead of inventing a plausible-sounding explanation.

set -e

discover_workspace() {
  local d="$PWD"
  while [ "$d" != "/" ]; do
    if [ -f "$d/.claude-plugin/marketplace.json" ] \
       || ls "$d"/outputs/stories/v* >/dev/null 2>&1; then
      echo "$d"
      return 0
    fi
    d=$(dirname "$d")
  done
  return 1
}

if [ -z "${WORKSPACE_ROOT:-}" ] \
   || [ "${WORKSPACE_ROOT:-}" = "{workspace_root}" ] \
   || [ ! -d "${WORKSPACE_ROOT:-}" ]; then
  if resolved=$(discover_workspace); then
    WORKSPACE_ROOT="$resolved"
  else
    WORKSPACE_ROOT="$PWD"
  fi
fi

USER_ARG="${1:-}"
# If the placeholder $USER_ARG never got substituted by the caller, treat it
# as empty rather than as a literal string to search for tokens in.
if [ "$USER_ARG" = "\$USER_ARG" ] || [ "$USER_ARG" = "{user_arg}" ]; then
  USER_ARG=""
fi

extract_token() {
  python3 -c "
import re, sys
s = sys.argv[1] if len(sys.argv) > 1 else ''
stories = re.findall(r'STORY-\d{2}-\d{3}', s)
if stories:
    seen, out = set(), []
    for tok in stories:
        if tok not in seen:
            seen.add(tok); out.append(tok)
    print(','.join(out))
else:
    m = re.search(r'EPIC-\d{2}|Sprint\s+\d+|sync-(?:contracts|infra|template|env|liquibase)', s)
    print(m.group(0) if m else s.strip())
" "$1"
}

if [ -n "$SKILL_ARG" ]; then
  echo "$SKILL_ARG"
  echo "SKILL_ARG"
  exit 0
fi

if [ -f "$WORKSPACE_ROOT/.skill-arg" ]; then
  val=$(cat "$WORKSPACE_ROOT/.skill-arg")
  rm -f "$WORKSPACE_ROOT/.skill-arg"
  echo "$val"
  echo ".skill-arg"
  exit 0
fi

if [ -n "$USER_ARG" ]; then
  echo "$(extract_token "$USER_ARG")"
  echo "conversational"
  exit 0
fi

if [ "$CLAUDE_AUTO_MODE" = "1" ] || [ -f "$WORKSPACE_ROOT/.auto-mode" ]; then
  echo "__AUTO__"
  echo "__AUTO__"
  exit 0
fi

echo ""
echo "EMPTY"
{
  echo "resolve_skill_arg.sh: no source resolved — diagnostics:"
  echo "  WORKSPACE_ROOT used: $WORKSPACE_ROOT"
  echo "  \$SKILL_ARG: ${SKILL_ARG:-<empty>}"
  if [ -f "$WORKSPACE_ROOT/.skill-arg" ]; then
    echo "  .skill-arg: PRESENT at $WORKSPACE_ROOT/.skill-arg (this should not happen — script would have consumed it; investigate)"
  else
    echo "  .skill-arg: absent at $WORKSPACE_ROOT/.skill-arg"
  fi
  echo "  \$1 (USER_ARG): ${1:-<empty>}"
  echo "  \$CLAUDE_AUTO_MODE: ${CLAUDE_AUTO_MODE:-<unset>}"
  if [ -f "$WORKSPACE_ROOT/.auto-mode" ]; then
    echo "  .auto-mode marker: PRESENT"
  else
    echo "  .auto-mode marker: absent"
  fi
} >&2
