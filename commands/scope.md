---
description: Run intake and scoping (aidlc-jira-fetcher and aidlc-scoper) to generate 00-scope.md
---

Use the `aidlc` skill to execute only the Scoping & Intake stage for the following request:
1. If the request contains a Jira ticket key (e.g. "PROJ-123"), delegate to `aidlc-jira-fetcher` first to pull ticket details.
2. Derive `<feature-slug>` and delegate to `aidlc-scoper` with tag `[STAGE:<feature-slug>:00-scope]` to classify the change and write `aidlc-docs/<feature-slug>/00-scope.md`.
3. Present the scope assessment, risk classification, and proposed stages to the user for approval. Once approved, record `00-scope` in `.gate-state.json` and stop without advancing to Inception or Construction.

Request: $ARGUMENTS
