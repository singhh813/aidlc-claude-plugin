---
description: Run the Inception phase (requirements, user stories, and architecture design) for an AIDLC feature
---

Use the `aidlc` skill to orchestrate the Inception phase for `<feature-slug>` based on the approved `00-scope.md`:
1. Delegate to `aidlc-requirements-analyst` with `[STAGE:<feature-slug>:01-requirements]` -> Review + Human Gate.
2. Delegate to `aidlc-story-writer` with `[STAGE:<feature-slug>:02-user-stories]` -> Review + Human Gate.
3. Delegate to `aidlc-architect` with `[STAGE:<feature-slug>:03-design]` -> Independent Review + Human Gate.
Record each approved stage in `.gate-state.json`. Stop after the architectural design gate is approved before entering Construction.

Feature / Request: $ARGUMENTS
