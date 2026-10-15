---
description: Run Dev Deployment Verification (check PR merge and execute API verification) for an AIDLC feature
---

Use the `aidlc` skill to orchestrate Dev Deployment Verification for `<feature-slug>` after a PR is opened:
1. Delegate to `aidlc-deploy-watcher` to check if the PR has merged into develop.
   - If not merged, inform the user and pause until deployment completes.
2. Once merged, obtain the dev base URL and auth credentials (if required).
3. Delegate to `aidlc-api-verifier` with `[STAGE:<feature-slug>:07-api-verification]` to author/update the Postman collection or test script and execute API verification requests via curl against the dev server.
4. Record `07-api-verification.md` and update `.gate-state.json` upon approval.
5. If verification succeeds, report results; if any test fails, coordinate targeted fixes with `aidlc-implementer` and `aidlc-pr-publisher`.

Feature / Request: $ARGUMENTS
