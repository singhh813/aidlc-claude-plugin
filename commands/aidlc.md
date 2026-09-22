---
description: Run the multi-agent AIDLC (AI-Driven Development Life Cycle) workflow for a feature or change
---

Use the `aidlc` skill to orchestrate the multi-agent AI-Driven Development Life Cycle workflow for the following request. Start at Step 0 (delegate to aidlc-scoper) and proceed through phases by delegating to the appropriate subagent at each step, per the aidlc skill's instructions — including running an independent `aidlc-reviewer` pass and pausing for human approval at each gate, unless this request says otherwise (e.g. contains `--no-review`/"skip review" to disable the reviewer for this run, or "run it all, don't stop for approval" to reduce human blocking on clean reviewer verdicts).

Request: $ARGUMENTS
