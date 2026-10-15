---
description: Run an independent audit on any AIDLC artifact, stage diff, or working-tree code using aidlc-reviewer
---

1. If the target/context contains a Jira ticket key (e.g. "PROJ-123"):
   - Delegate to `aidlc-jira-fetcher` first: "Fetch <KEY> and extract its summary and acceptance criteria."
   - Pass the fetched ticket acceptance criteria as the reference specification to review against.
2. Delegate to `aidlc-reviewer` to perform an independent, read-only audit of the specified artifact, stage, or changes:
   - Pass the target file path (under `aidlc-docs/<feature-slug>/`) or code diff.
   - Pass upstream reference artifacts and/or Jira acceptance criteria for context.
   - Output the reviewer's verdict (`approve`, `approve with notes`, `needs changes`) and prioritized issue list directly to the user.

Target / Context: $ARGUMENTS
