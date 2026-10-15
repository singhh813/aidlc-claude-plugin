---
description: Run the Operations phase (deployment, rollback, and monitoring plan) for an AIDLC feature
---

Use the `aidlc` skill to orchestrate the Operations phase for `<feature-slug>`:
1. Verify that `00-scope.md` marked Operations as active.
2. Delegate to `aidlc-ops-planner` with `[STAGE:<feature-slug>:08-operations]` to inspect existing repository CI/CD configs, Dockerfiles, and observability setup and write `aidlc-docs/<feature-slug>/08-operations.md`.
3. Delegate to `aidlc-reviewer` with stage `08-operations` to evaluate the operations plan against actual repository infrastructure and architectural risks.
4. Present the operations plan and review verdict to the human for approval.
5. Once approved, record `08-operations` in `.gate-state.json` and conclude the feature lifecycle.

Feature / Request: $ARGUMENTS
