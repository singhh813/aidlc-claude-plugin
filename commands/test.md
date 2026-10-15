---
description: Direct test generation mode — plans coverage matrix, pauses for approval, and writes/executes tests
---

1. If the target/request contains a Jira ticket key (e.g. "PROJ-123"):
   - Delegate to `aidlc-jira-fetcher` first: "Fetch <KEY> and extract its acceptance criteria for test planning."
   - Extract the restated request and acceptance criteria from `aidlc-jira-fetcher` to use as the testing target.
2. Delegate directly to `aidlc-tester` with the `[STANDALONE:test]` tag:
   - Inspect the target code or recent diff and outline a test coverage matrix mapped to acceptance criteria (unit, integration, edge cases, mocking strategy).
   - For non-trivial test generation, present the plan and pause for user approval.
   - Once approved, write and run tests using the project's test runner (e.g. pytest, vitest, go test, cargo test) and static type checks.
No prior AIDLC stages or `aidlc-docs/` artifacts are required.

Target / Request: $ARGUMENTS
