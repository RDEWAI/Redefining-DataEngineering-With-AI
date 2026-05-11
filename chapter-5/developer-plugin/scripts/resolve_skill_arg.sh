#!/usr/bin/env bash
# Resolves a skill's target argument from the four canonical sources, in order:
#   1. $SKILL_ARG environment variable
#   2. {workspace_root}/.skill-arg file (consumed; deleted after read)
#   3. Conversational argument supplied as $1 (the user message)
#   4. $CLAUDE_AUTO_MODE=1 or {workspace_root}/.auto-mode marker -> "__AUTO__"
#
# Prints two lines on stdout:
#   <resolved_value>
#   <source: SKILL_ARG | .skill-arg | conversational | __AUTO__ | EMPTY>
#
# If the conversational arg is verbose (a sentence rather than a bare token),
# extracts the first STORY-NN-NNN / EPIC-NN / "Sprint N" token from it.
#
# Usage:
#   eval "$(WORKSPACE_ROOT=/path/to/chapter-5 \
#     bash resolve_skill_arg.sh "$USER_ARG" | \
#     awk 'NR==1{print "RESOLVED_ARG=\""$0"\""} NR==2{print "RESOLVED_SOURCE=\""$0"\""}')"

set -e

WORKSPACE_ROOT="${WORKSPACE_ROOT:-$PWD}"
USER_ARG="$1"

extract_token() {
  # Pull first STORY-NN-NNN, EPIC-NN, or "Sprint N" from $1
  python3 -c "
import re, sys
s = sys.argv[1] if len(sys.argv) > 1 else ''
m = re.search(r'STORY-\d{2}-\d{3}|EPIC-\d{2}|Sprint\s+\d+|sync-(?:contracts|infra|template|env)', s)
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
