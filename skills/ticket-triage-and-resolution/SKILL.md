---
name: ticket-triage-and-resolution
description: Systematic methodology for triaging tickets, distinguishing between bug reports and implementation/feature requests, and executing the appropriate resolution workflow. Use whenever assessing incoming tickets or bug reports, diagnosing root causes, determining whether an issue is a bug or feature enhancement, applying surgical bug fixes with regression tests, or executing implementation tickets.
---

# Ticket Triage & Resolution: Bug vs. Implementation

Misclassifying tickets leads to poor estimation, bloated pull requests, and recurring regressions. This skill provides a definitive classification taxonomy and structured, distinct execution workflows for bug fixes versus feature implementations.

---

## 1. Classification Taxonomy: Bug vs. Implementation

Before taking action on any ticket, apply this classification criteria:

### Definitive Definitions

| Dimension | Bug Fix | Implementation (Feature / Story) |
| :--- | :--- | :--- |
| **Definition** | A defect where the software deviates from documented specification, existing contract, or intended design. | A request to add new functionality, alter business logic, or expand existing capabilities. |
| **System State** | System is broken, returning erroneous data, crashing (500), leaking resources, or failing contract. | System is behaving as originally designed, but requirements have evolved or expanded. |
| **Baseline** | Restores established baseline. | Establishes a new baseline. |
| **Test Strategy** | **Test-First**: Automated test must reproduce defect and fail *before* code change. | **Test-Driven / Concurrent**: Tests written to validate new acceptance criteria. |
| **Code Scope** | **Surgical & Minimal**: Fixes root cause only; no opportunistic refactoring. | **Modular & Holistic**: Follows full design, architecture, schemas, and services. |

### The "Grey Zone" Decision Matrix

| Scenario / Symptom | Classification | Rationale |
| :--- | :--- | :--- |
| **Endpoint returns 500 on unexpected user input** | **Bug** | Unhandled exceptions and server crashes are always bugs; input should yield a 422/400 validation error. |
| **API returns correct data, but client wants a new filter parameter** | **Implementation** | The existing contract is intact; adding new query filters is a feature extension. |
| **Performance degraded from 50ms to 800ms after last release** | **Bug (Regression)** | Performance regressions violating established SLAs are bugs. |
| **User expected button to do X, but PRD and spec clearly say Y** | **Implementation / Change Request** | System works as designed; changing business logic requires product approval. |
| **Missing authentication check allows unauthorized record access** | **Bug (Security Defect)** | Violates security baseline and data integrity expectations. |
| **Database column allows NULL when application logic assumes non-null** | **Bug** | Schema constraint mismatch leading to runtime corruption. |

---

## 2. Classification Flowchart

```
                 Incoming Ticket / Request
                            |
           Is current behavior crashing, throwing 500,
           returning incorrect data, or violating spec?
                         /     \
                       YES      NO
                       /         \
         Did it previously work  Is this modifying established rules
         or violate acceptance   or requesting net-new capabilities?
               criteria?                  /              \
                /     \                 YES               NO
              YES      NO                /                 \
              /         \          [Feature /         [Documentation /
      [Regression]   [Defect]    Implementation]       Clarification]
           \             /
            \           /
             v         v
        === BUG WORKFLOW ===
```

---

## 3. The Bug Resolution Workflow

Bug fixes must follow a strict, disciplined 6-step lifecycle. **Never fix code before reproducing the bug with a failing test.**

### Step 1: Reproduce & Isolate (MRE)
- Reproduce the failure reliably with a Minimal Reproducible Example (MRE).
- Document:
  - Exact request payload, query params, headers.
  - Initial system state (database records, auth user role).
  - Observed behavior vs. Expected behavior.
  - Stack trace and server logs.

### Step 2: Regression Isolation
- Investigate whether the behavior was recently introduced:
  - Check `git log -S <symbol>` or `git log -p <file>` to identify the introducing commit.
  - Use `git bisect` if the introduction point is unknown across releases.

### Step 3: Root Cause Analysis (RCA)
- Apply the **5 Whys** method to find the root flaw rather than patching the symptom:
  - *Symptom*: `AttributeError: 'NoneType' object has no attribute 'status'`
  - *Why 1*: Order query returned `None`.
  - *Why 2*: Order was soft-deleted in a parallel transaction.
  - *Why 3*: The service method did not check for active status before accessing properties.
  - *Root Cause*: Missing state validation and lack of database row-level locking.

### Step 4: Write Failing Regression Test First (RED Phase)
Write an automated unit or integration test that reproduces the exact scenario.
- **Run the test**: Verify it **FAILS** with the exact error reported in the ticket.
- If the test passes immediately, you have not reproduced the bug. Do not proceed to the fix until the test fails.

```python
# tests/test_order_bug_regression.py
import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_regression_order_cancellation_race_condition(client: AsyncClient, mock_db_with_soft_deleted_order):
    """
    REGRESSION TEST for TICKET-402:
    Cancelling a soft-deleted order should return 404 rather than 500 NullReference.
    """
    response = await client.post("/api/v1/orders/999/cancel")
    
    # Prior to fix: Crashed with 500 Internal Server Error
    # Expected after fix: Clean 404 Not Found
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "ORDER_NOT_FOUND"
```

### Step 5: Minimal Surgical Fix (GREEN Phase)
- Apply the smallest, lowest-risk code change that addresses the root cause.
- **Strict Rule**: Do not reformat unrelated files, upgrade dependencies, or refactor surrounding code in a bug fix PR. This keeps the PR diff easy to audit and minimizes risk of secondary regressions.

### Step 6: Verify & Protect
- Run the reproduction test: Verify it now **PASSES**.
- Run the full project test suite: Verify zero collateral breakage.
- Run static checks: `ruff check` and `mypy`.

---

## 4. The Implementation / Feature Workflow

Feature tickets introduce new capabilities and require structured architecture, design, and multi-tier testing.

```
[Requirements Review] 
       │
       ▼
[Design & Contract Spec]  ──► (API Router, Schemas, DB Models, Migrations)
       │
       ▼
[Phased Implementation]   ──► (Repo -> Service -> Controller / Endpoint)
       │
       ▼
[Comprehensive Testing]   ──► (Unit tests + Integration tests + Negative paths)
       │
       ▼
[Docs & Verification]     ──► (OpenAPI schema, changelog, migration scripts)
```

### Step 1: Requirements & Contract Definition
- Confirm all acceptance criteria are documented in Gherkin format (`Given/When/Then`).
- Verify data model changes, database indexes, and migration compatibility.
- Ensure backwards compatibility for external API consumers.

### Step 2: Layered Construction Order
Implement changes from the bottom up to ensure modular testability:
1. **Database / Models**: Add tables, columns, indexes, and Alembic migrations.
2. **Schemas**: Define Pydantic v2 request/response models with validation rules.
3. **Repository / Data Access**: Add database query methods with unit tests.
4. **Service Layer**: Implement pure business logic and transactional boundaries.
5. **API Router**: Wire endpoints, HTTP status codes, and dependency injections.

### Step 3: Complete Acceptance Testing
- Implement unit tests for service layer business rules.
- Implement integration tests covering:
  - Happy Path (200 / 201).
  - Validation Failures (422).
  - Auth / Permission Checks (401 / 403).
  - Not Found & Conflict Scenarios (404 / 409).

---

## 5. Anti-Patterns & Pitfalls

| Anti-Pattern | Why It Fails | Correct Approach |
| :--- | :--- | :--- |
| **Symptom Patching** | Adding `if x is None: return` without understanding why `x` was `None`. Defect reappears elsewhere. | Perform Root Cause Analysis (5 Whys) and fix where the invalid state originates. |
| **Swallowing Exceptions** | Wrapping failing code in `try: ... except Exception: pass` to make the error disappear. | Handle specific expected exceptions; let unexpected errors surface to monitoring. |
| **No Regression Test** | Fixing code without committing an automated test. The bug will inevitably be reintroduced later. | Commit the automated reproduction test alongside the fix. |
| **Scope Creep in Hotfixes** | Refactoring entire modules or tweaking styles while fixing a P0 defect. | Keep bug fixes strictly surgical. Log refactorings as separate implementation tickets. |
| **Feature in Bug Clothing** | User calls a missing feature a "bug" to skip planning and jump priority. | Politely reclassify as an enhancement/story and scope acceptance criteria. |

---

## 6. Pre-Commit Checklist

### For Bug Fixes
- [ ] Root cause identified and verified (not just patching the symptom).
- [ ] Automated regression test written that failed before the fix and passes with it.
- [ ] Diff is strictly scoped to the fix (no opportunistic refactoring or reformatting).
- [ ] Full regression test suite passes cleanly.
- [ ] PR description cites ticket key, RCA summary, and reproduction steps.

### For Implementation Tickets
- [ ] All acceptance criteria met and verified by automated tests.
- [ ] Pydantic v2 schemas and validation models defined.
- [ ] Database migrations are backwards-compatible.
- [ ] Unit and integration tests cover nominal and edge case paths.
- [ ] Linting, type checks, and security audits pass.
