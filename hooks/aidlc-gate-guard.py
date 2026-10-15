#!/usr/bin/env python3
"""
hooks/aidlc-gate-guard.py

PreToolUse hook for Task and Agent tool calls in the AIDLC multi-agent system.
Enforces AIDLC stage sequencing: a delegation to a stage-producing subagent
must be tagged "[STAGE:<feature-slug>:<stage-id>]" as the first line of its prompt,
and that stage must be the legitimate next step after
aidlc-docs/<feature-slug>/.gate-state.json's last_approved_stage.

Deliberately dependency-free (standard library json, sys, re, os, pathlib).
Works identically across Windows, macOS, and Linux.
"""

import json
import os
import re
import sys
from pathlib import Path

STAGES = [
    "00-scope",
    "01-requirements",
    "02-user-stories",
    "03-design",
    "04-implementation-plan",
    "04-implementation-code",
    "05-test-plan",
    "05-test-results",
    "06-pr-plan",
    "07-api-verification",
    "08-operations",
]

STAGE_PRODUCING_AGENTS = {
    "aidlc-scoper",
    "aidlc-requirements-analyst",
    "aidlc-story-writer",
    "aidlc-architect",
    "aidlc-implementer",
    "aidlc-tester",
    "aidlc-pr-publisher",
    "aidlc-api-verifier",
    "aidlc-ops-planner",
}


def emit_decision(decision: str, reason: str) -> None:
    output = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": decision,
            "permissionDecisionReason": reason,
        }
    }
    print(json.dumps(output))
    sys.exit(0)


def allow(reason: str) -> None:
    emit_decision("allow", reason)


def deny(reason: str) -> None:
    emit_decision("deny", reason)


def extract_prompt_text(data: dict) -> str:
    """Extracts prompt text from standard tool_input shapes."""
    if not isinstance(data, dict):
        return ""

    candidates = [data]
    if "tool_input" in data and isinstance(data["tool_input"], dict):
        candidates.insert(0, data["tool_input"])

    for candidate in candidates:
        for field in ("prompt", "description", "message", "instruction", "task"):
            val = candidate.get(field)
            if isinstance(val, str) and val.strip():
                return val.strip()

    return ""


def extract_subagent_name(data: dict) -> str:
    """Extracts target subagent name or type from standard tool_input shapes."""
    if not isinstance(data, dict):
        return ""

    candidates = [data]
    if "tool_input" in data and isinstance(data["tool_input"], dict):
        candidates.insert(0, data["tool_input"])

    for candidate in candidates:
        for field in ("subagent_type", "subagent", "agent_name", "agent", "name", "type"):
            val = candidate.get(field)
            if isinstance(val, str) and val.strip():
                return val.strip()

    return ""


def main() -> None:
    try:
        raw_input = sys.stdin.read()
        if not raw_input.strip():
            allow("aidlc-gate-guard: empty input received — allowing without check.")
        data = json.loads(raw_input)
    except Exception as e:
        deny(f"aidlc-gate-guard: failed to parse JSON input from hook event: {e}")
        return

    subagent_name = extract_subagent_name(data)
    prompt_text = extract_prompt_text(data)

    if not prompt_text:
        if subagent_name in STAGE_PRODUCING_AGENTS:
            deny(
                f"aidlc-gate-guard: delegation to stage-producing subagent '{subagent_name}' "
                "missing required prompt and [STAGE:<feature-slug>:<stage-id>] tag."
            )
            return
        allow("aidlc-gate-guard: no recognizable prompt field on this delegation — allowing.")
        return

    lines = [line.strip() for line in prompt_text.splitlines() if line.strip()]
    first_line = lines[0] if lines else ""

    # Standalone mode: allows direct execution of agents without stage gates
    standalone_match = re.match(r"^\[STANDALONE(?::([^\]]+))?\]", first_line, re.IGNORECASE)
    if standalone_match:
        mode = standalone_match.group(1) or "general"
        allow(
            f"aidlc-gate-guard: standalone mode '{mode}' active — allowing direct execution without stage gates."
        )
        return

    match = re.match(r"^\[STAGE:([^:]+):([A-Za-z0-9_-]+)\]", first_line)

    if not match:
        if subagent_name in STAGE_PRODUCING_AGENTS:
            deny(
                f"aidlc-gate-guard: delegation to stage-producing subagent '{subagent_name}' "
                "must begin with '[STAGE:<feature-slug>:<stage-id>]'. Tag was missing or malformed."
            )
            return
        allow(
            f"aidlc-gate-guard: subagent '{subagent_name or 'unspecified'}' without [STAGE:...] tag — "
            "not a gated AIDLC stage delegation."
        )
        return

    feature_slug = match.group(1).strip()
    requested_stage = match.group(2).strip()

    if requested_stage not in STAGES:
        deny(
            f"aidlc-gate-guard: '{requested_stage}' is not a recognized AIDLC stage id. "
            f"Valid stages in sequence: {', '.join(STAGES)}"
        )
        return

    req_idx = STAGES.index(requested_stage)
    state_file = Path("aidlc-docs") / feature_slug / ".gate-state.json"

    if not state_file.exists():
        if req_idx == 0:
            allow("aidlc-gate-guard: first stage (00-scope) for a new feature — no prior state required.")
            return
        deny(
            f"aidlc-gate-guard: no {state_file} found, but requested stage '{requested_stage}' "
            "is not the first stage. Run 00-scope first, or create .gate-state.json if prior stages ran earlier."
        )
        return

    try:
        with open(state_file, "r", encoding="utf-8") as f:
            state_data = json.load(f)
    except Exception as e:
        deny(f"aidlc-gate-guard: failed to read state file {state_file}: {e}")
        return

    enforcement = state_data.get("enforcement", "on")
    if enforcement == "off":
        allow("aidlc-gate-guard: enforcement is off for this run (review/gate skipped by human request).")
        return

    # 1. Human review override: human authority supersedes LLM gate guard
    if state_data.get("human_reviewed") is True:
        allow(
            f"aidlc-gate-guard: human_reviewed is enabled — allowing stage '{requested_stage}' under human authority."
        )
        return

    last_approved = state_data.get("last_approved_stage", "none")
    if last_approved == "none":
        if req_idx == 0:
            allow("aidlc-gate-guard: no stage approved yet — 00-scope may proceed.")
            return
        deny(
            f"aidlc-gate-guard: {state_file} shows no stage approved yet, but requested stage "
            f"'{requested_stage}' is not first. Complete and record approval of 00-scope first."
        )
        return

    if last_approved not in STAGES:
        deny(
            f"aidlc-gate-guard: {state_file}'s last_approved_stage ('{last_approved}') "
            "is not a recognized stage id — fix the state file before proceeding."
        )
        return

    last_idx = STAGES.index(last_approved)

    # 2. Standard progression: allow re-running the current stage (revisions), or moving forward by at most 1 step.
    if req_idx <= last_idx + 1:
        allow(
            f"aidlc-gate-guard: '{requested_stage}' is a valid next/current stage after last-approved '{last_approved}'."
        )
        return

    # 3. Risk-Adaptive Fast-Track Mode: permits skipping Inception / intermediate planning stages
    mode = state_data.get("mode", "normal")
    risk = state_data.get("risk", "high")
    is_fast_track = mode == "fast-track" or risk == "low"

    if is_fast_track:
        fast_track_allowed_targets = {
            "00-scope": [
                "01-requirements",
                "02-user-stories",
                "03-design",
                "04-implementation-plan",
                "04-implementation-code",
            ],
            "01-requirements": [
                "02-user-stories",
                "03-design",
                "04-implementation-plan",
                "04-implementation-code",
            ],
            "02-user-stories": [
                "03-design",
                "04-implementation-plan",
                "04-implementation-code",
            ],
            "03-design": ["04-implementation-plan", "04-implementation-code"],
            "04-implementation-plan": ["04-implementation-code", "05-test-plan"],
            "04-implementation-code": ["05-test-plan", "05-test-results", "06-pr-plan"],
            "05-test-plan": ["05-test-results", "06-pr-plan"],
            "05-test-results": ["06-pr-plan", "07-api-verification", "08-operations"],
            "06-pr-plan": ["07-api-verification", "08-operations"],
            "07-api-verification": ["08-operations"],
        }
        allowed_list = fast_track_allowed_targets.get(last_approved, [])
        if requested_stage in allowed_list:
            allow(
                f"aidlc-gate-guard: '{requested_stage}' is permitted in fast-track/low-risk mode after '{last_approved}'."
            )
            return

    deny(
        f"aidlc-gate-guard: requested stage '{requested_stage}' skips ahead of last-approved stage "
        f"'{last_approved}' in {state_file}. Complete and record approval of intervening stage(s) first "
        "(or enable fast-track/low-risk mode in .gate-state.json for low-risk changes)."
    )


if __name__ == "__main__":
    main()
