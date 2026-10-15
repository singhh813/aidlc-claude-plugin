---
description: Run the Delivery phase (plan commit/branch/PR, review, and open pull request) for an AIDLC feature
---

Use the `aidlc` skill to orchestrate the Delivery phase (PR Publishing) for `<feature-slug>` after construction and tests have passed:
1. Delegate to `aidlc-pr-publisher` with `[STAGE:<feature-slug>:06-pr-plan]`: plan the branch, files to stage, commit message, and PR title/body — do not publish yet.
2. Delegate to `aidlc-reviewer` with stage `06-pr-plan` to verify the proposed branch/commit/PR description against the actual git diff.
3. Present the PR plan and review verdict to the human for explicit approval.
4. Once approved, record `06-pr-plan` in `.gate-state.json` and resume `aidlc-pr-publisher` to commit, push, and open the GitHub PR.
5. Report the PR URL and note the PR number for downstream deployment verification.

Feature / Request: $ARGUMENTS
