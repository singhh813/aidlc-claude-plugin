---
description: Direct test generation mode — plans coverage matrix, pauses for approval, and writes/executes tests
---

Delegate directly to `aidlc-tester` with the `[STANDALONE:test]` tag:
1. Inspect the target code or recent diff and outline a test coverage matrix (unit, integration, edge cases, mocking strategy).
2. For non-trivial test generation, present the plan and pause for user approval.
3. Once approved, write and run tests using the project's test runner (e.g. pytest, vitest, go test, cargo test) and static type checks.
No prior AIDLC stages or `aidlc-docs/` artifacts are required.

Target / Request: $ARGUMENTS
