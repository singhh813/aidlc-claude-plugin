---
description: Run the Construction phase (implementation planning, coding, test planning, and testing) for an AIDLC feature
---

Use the `aidlc` skill to orchestrate the Construction phase for `<feature-slug>` based on the approved `03-design.md`:
1. Delegate to `aidlc-implementer` with `[STAGE:<feature-slug>:04-implementation-plan]` (Plan only) -> Review + Human Gate.
2. Resume `aidlc-implementer` with `[STAGE:<feature-slug>:04-implementation-code]` to implement code -> Independent Review (`aidlc-reviewer`) + Human Gate.
3. Delegate to `aidlc-tester` with `[STAGE:<feature-slug>:05-test-plan]` (Test plan only) -> Review + Human Gate.
4. Resume `aidlc-tester` with `[STAGE:<feature-slug>:05-test-results]` to write and execute tests -> Independent Review (`aidlc-reviewer`) + Human Gate.
Record each approved stage in `.gate-state.json`. Stop after all tests pass before opening a Pull Request.

Feature / Request: $ARGUMENTS
