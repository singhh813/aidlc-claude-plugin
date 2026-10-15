---
description: Run an independent audit on any AIDLC artifact, stage diff, or working-tree code using aidlc-reviewer
---

Delegate to `aidlc-reviewer` to perform an independent, read-only audit of the specified artifact, stage, or changes:
- Pass the target file path (under `aidlc-docs/<feature-slug>/`) or code diff.
- Pass upstream reference artifacts for context.
- Output the reviewer's verdict (`approve`, `approve with notes`, `needs changes`) and prioritized issue list directly to the user.

Target / Context: $ARGUMENTS
