---
description: Direct development mode — plans for complex tasks, pauses for approval, and implements code with linters
---

1. If the request is or contains a Jira ticket key (e.g. "PROJ-123"):
   - Delegate to `aidlc-jira-fetcher` first: "Fetch <KEY> and restate it as a development task."
   - Extract the restated request, acceptance criteria, and issue type from `aidlc-jira-fetcher`.
   - Use that as the task input for implementation.
2. Delegate to `aidlc-implementer` with the `[STANDALONE:dev]` tag:
   - For trivial changes: implement directly and format.
   - For complex changes: plan first (affected files, change sequence, database changes, risks), pause for user approval, and once approved write the code and run linters.
No prior AIDLC stages or `aidlc-docs/` artifacts are required.

Task / Request: $ARGUMENTS
