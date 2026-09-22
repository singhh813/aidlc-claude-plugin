#!/bin/bash
# .claude/hooks/aidlc-gate-guard.sh
#
# PreToolUse hook on subagent-delegation tool calls (matcher: Task, and/or
# Agent — see settings.json comment). Enforces AIDLC stage sequencing: a
# delegation to a stage-producing subagent must be tagged
# "[STAGE:<feature-slug>:<stage-id>]" as the first line of its prompt, and
# that stage must be the legitimate next step after
# aidlc-docs/<feature-slug>/.gate-state.json's last_approved_stage.
#
# This exists because prompt-based orchestration alone can silently skip a
# gate; this hook makes skipping mechanically impossible instead of merely
# discouraged. See skills/aidlc/SKILL.md "Hard gate enforcement."
#
# Deliberately dependency-free (no jq) — parses the flat JSON shapes it
# needs with grep/sed. If tool_input's real field names differ from the
# ones checked below, extend PROMPT_TEXT's fallbacks rather than adding a
# JSON library dependency.
set -euo pipefail

INPUT="$(cat)"

allow() {
  printf '{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"allow","permissionDecisionReason":%s}}\n' "$(json_escape "$1")"
  exit 0
}

deny() {
  printf '{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"deny","permissionDecisionReason":%s}}\n' "$(json_escape "$1")"
  exit 0
}

# Minimal JSON string escaper (backslash, double-quote, newlines) — enough
# for the plain-ASCII reason strings this script emits itself.
json_escape() {
  local s="$1"
  s="${s//\\/\\\\}"
  s="${s//\"/\\\"}"
  s="${s//$'\n'/\\n}"
  printf '"%s"' "$s"
}

# Extracts the string value of a top-level-ish JSON field by name from a
# blob, tolerating nesting one level deep (e.g. "tool_input":{"prompt":"...").
# Not a general JSON parser: assumes the value is a JSON string (quoted),
# handles escaped quotes inside it, and takes the first match.
json_field() {
  local field="$1" blob="$2"
  printf '%s' "$blob" | { grep -oP '"'"$field"'"\s*:\s*"(\\.|[^"\\])*"' || true; } | head -1 \
    | sed -E 's/^"'"$field"'"\s*:\s*"//; s/"$//' \
    | sed -E 's/\\"/"/g; s/\\n/\n/g; s/\\\\/\\/g'
}

# Ordered stage sequence. Index in this array = required position.
STAGES=(00-scope 01-requirements 02-user-stories 03-design 04-implementation-plan 04-implementation-code 05-test-plan 05-test-results 06-pr-plan 07-api-verification 08-operations)

stage_index() {
  local target="$1"
  for i in "${!STAGES[@]}"; do
    if [ "${STAGES[$i]}" = "$target" ]; then
      echo "$i"
      return 0
    fi
  done
  echo "-1"
}

# Try a few likely field paths for the delegation's prompt text — this
# harness's exact Task/Agent tool_input shape isn't confirmed, so check
# several rather than silently failing to find any.
PROMPT_TEXT="$(json_field "prompt" "$INPUT")"
if [ -z "$PROMPT_TEXT" ]; then
  PROMPT_TEXT="$(json_field "description" "$INPUT")"
fi
if [ -z "$PROMPT_TEXT" ]; then
  PROMPT_TEXT="$(json_field "message" "$INPUT")"
fi

if [ -z "$PROMPT_TEXT" ]; then
  # Can't find prompt text to check — fail OPEN with a visible warning
  # rather than blocking unrelated tool calls this hook was never meant to
  # gate (e.g. a non-AIDLC subagent delegation with a different shape).
  allow "aidlc-gate-guard: no recognizable prompt field on this delegation — allowing without a stage check. If this was an AIDLC stage delegation, the hook's field lookup needs updating."
fi

# No stage tag at all — not an AIDLC-gated delegation (e.g. aidlc-jira-fetcher,
# aidlc-reviewer, or a non-AIDLC subagent). Let it through untouched.
TAG_LINE="$(printf '%s\n' "$PROMPT_TEXT" | head -1)"
if ! printf '%s' "$TAG_LINE" | grep -qE '^\[STAGE:[^:]+:[A-Za-z0-9_-]+\]'; then
  allow "aidlc-gate-guard: no [STAGE:...] tag — not a gated AIDLC stage delegation."
fi

FEATURE_SLUG="$(printf '%s' "$TAG_LINE" | sed -E 's/^\[STAGE:([^:]+):([A-Za-z0-9_-]+)\].*/\1/')"
REQUESTED_STAGE="$(printf '%s' "$TAG_LINE" | sed -E 's/^\[STAGE:([^:]+):([A-Za-z0-9_-]+)\].*/\2/')"

REQ_IDX="$(stage_index "$REQUESTED_STAGE")"
if [ "$REQ_IDX" = "-1" ]; then
  deny "aidlc-gate-guard: '$REQUESTED_STAGE' is not a recognized AIDLC stage id. Check the tag against skills/aidlc/SKILL.md's stage list."
fi

STATE_FILE="aidlc-docs/${FEATURE_SLUG}/.gate-state.json"

if [ ! -f "$STATE_FILE" ]; then
  if [ "$REQ_IDX" -eq 0 ]; then
    allow "aidlc-gate-guard: first stage (00-scope) for a new feature — no prior state required."
  fi
  deny "aidlc-gate-guard: no $STATE_FILE found, but requested stage '$REQUESTED_STAGE' is not the first stage. Run 00-scope first, or write .gate-state.json if this feature's earlier stages ran before this hook existed."
fi

STATE_CONTENT="$(cat "$STATE_FILE" 2>/dev/null || echo '{}')"

ENFORCEMENT="$(json_field "enforcement" "$STATE_CONTENT")"
if [ -z "$ENFORCEMENT" ]; then
  ENFORCEMENT="on"
fi
if [ "$ENFORCEMENT" = "off" ]; then
  allow "aidlc-gate-guard: enforcement is off for this run (review/gate skipped by human request)."
fi

LAST_APPROVED="$(json_field "last_approved_stage" "$STATE_CONTENT")"
if [ -z "$LAST_APPROVED" ]; then
  LAST_APPROVED="none"
fi

if [ "$LAST_APPROVED" = "none" ]; then
  if [ "$REQ_IDX" -eq 0 ]; then
    allow "aidlc-gate-guard: no stage approved yet — 00-scope may proceed."
  fi
  deny "aidlc-gate-guard: $STATE_FILE shows no stage approved yet, but requested stage '$REQUESTED_STAGE' isn't first. Complete and record approval of 00-scope first."
fi

LAST_IDX="$(stage_index "$LAST_APPROVED")"
if [ "$LAST_IDX" = "-1" ]; then
  deny "aidlc-gate-guard: $STATE_FILE's last_approved_stage ('$LAST_APPROVED') isn't a recognized stage id — fix the state file before proceeding."
fi

# Allow re-running the same stage (e.g. a revision after "needs changes"),
# or moving forward exactly one step. Anything further ahead means a stage
# was skipped.
if [ "$REQ_IDX" -le "$((LAST_IDX + 1))" ]; then
  allow "aidlc-gate-guard: '$REQUESTED_STAGE' is a valid next/current stage after last-approved '$LAST_APPROVED'."
fi

deny "aidlc-gate-guard: requested stage '$REQUESTED_STAGE' skips ahead of last-approved stage '$LAST_APPROVED' in $STATE_FILE. Complete and record approval of the intervening stage(s) first — don't reorder .gate-state.json to route around this."
