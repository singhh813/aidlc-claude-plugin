---
name: story-writing-and-scoping
description: Framework and guidelines for scoping software initiatives and authoring high-quality user stories with testable acceptance criteria. Use whenever breaking down user requests or Jira tickets, determining project scope boundaries, estimating complexity, defining In-Scope vs Out-of-Scope items, identifying edge cases, or writing INVEST-compliant user stories with Gherkin (Given/When/Then) acceptance criteria.
---

# Story Writing & Scoping Framework

High-quality software delivery begins with unambiguous scoping and testable user stories. This skill provides product managers, architects, and software engineers with a rigorous methodology to define scope, eliminate ambiguity, and author INVEST-compliant user stories.

---

## 1. Scoping Framework

Before writing code or stories, determine the exact boundaries of the initiative.

### The 4 Pillars of Scoping

1. **Problem Statement & Objectives**:
   - What core user pain or business need is being solved?
   - What is the measurable metric of success (e.g., latency reduction, conversion rate, compliance)?
2. **In-Scope vs. Explicitly Out-of-Scope**:
   - *In-Scope*: Features and behaviors guaranteed to be delivered in this milestone.
   - *Out-of-Scope*: Related items deliberately deferred to future phases. **Explicitly listing what will NOT be done is the primary weapon against scope creep.**
3. **Assumptions & Technical Constraints**:
   - Upstream service availability, database schemas, supported client versions, authentication dependencies.
4. **Risk & Dependency Matrix**:
   - Identify third-party dependencies, breaking schema changes, performance risks, and mitigation strategies.

### Scope Sizing Heuristics

| Tier | Characteristics | Process Recommendation |
| :--- | :--- | :--- |
| **Trivial** | 1–2 files, isolated bugfix, typo, or minor parameter update. | Skip formal stories; execute directly with a targeted test. |
| **Lean** | 1–3 endpoints or 1 service, clearly understood behavior, < 5 story points. | Abbreviated design, 1–3 concise user stories with Gherkin criteria. |
| **Full** | Multi-service, new data models, external integrations, > 5 story points. | Complete scoping doc, architecture review, decomposed user story backlog. |

---

## 2. Story Sizing & Estimation Guidelines

Estimate complexity using modified Fibonacci story points:

- **1 Point**: Trivial change. Minor schema column addition, simple validation update, trivial configuration change.
- **2 Points**: Simple feature. Standard CRUD endpoint with existing patterns, straightforward unit tests.
- **3 Points**: Moderate complexity. New endpoint with database queries, multiple validation paths, unit & integration tests.
- **5 Points**: High complexity. Multi-step business workflow, complex business logic, external API integration with error handling.
- **8 Points**: Very complex. Cross-cutting concern, new architectural component, complex data migration. **Strong candidate for splitting.**
- **13+ Points**: Epic. Must be split into smaller vertical slices before construction.

---

## 3. User Story Authoring & INVEST Principles

Every user story must follow the standard persona-driven format:

```text
As a <specific user role/persona>,
I want <capability or action>,
So that <business value or benefit>.
```

### The INVEST Checklist

- **I - Independent**: Can be developed, tested, and shipped in any order without blocking other stories.
- **N - Negotiable**: Captures the essence of what is needed, leaving implementation details open to engineering collaboration.
- **V - Valuable**: Delivers demonstrable value to an end user, customer, or business stakeholder.
- **E - Estimable**: Clear enough that engineers can forecast effort without open unknowns.
- **S - Small**: Sized to complete within a couple of days (typically 1 to 5 points).
- **T - Testable**: Possesses clear, unambiguous criteria that automated tests can verify.

### Vertical Slicing vs. Horizontal Slicing

⛔ **Anti-Pattern (Horizontal Slicing)**:
- Story 1: "Create database tables for orders" (No user value on its own)
- Story 2: "Create backend API endpoints for orders"
- Story 3: "Create frontend UI for orders"

✅ **Best Practice (Vertical Slicing)**:
- Story 1: "Place order with credit card (End-to-End: DB + API + UI basic happy path)"
- Story 2: "Support order cancellation within 15 minutes"
- Story 3: "Support discount code application during checkout"

---

## 4. Acceptance Criteria with Gherkin BDD

Acceptance criteria define the exact conditions under which a story is considered complete. Use the Gherkin BDD structure (`Given... When... Then...`).

### Mandatory Scenario Coverage Matrix
For every user story, author scenarios for:
1. **Happy Path (Nominal Flow)**: Standard successful execution.
2. **Alternative Paths**: Secondary valid inputs, optional fields, pagination.
3. **Negative & Error Paths**: Validation failures, missing credentials, duplicate records.
4. **Edge Cases**: Empty states, maximum limits, concurrency conflicts.
5. **Non-Functional Requirements (NFRs)**: Response latency, rate limits, audit logging.

### Example User Story with Acceptance Criteria

```markdown
### US-101: Cancel Pending Order

**Story**:
As a registered customer,
I want to cancel an order that is still in "Pending" status,
So that I am not charged for an accidental purchase.

**Story Points**: 3
**Tags**: Orders, Checkout, Customer-Facing

---

#### Acceptance Criteria

**Scenario 1: Successful cancellation of pending order (Happy Path)**
- **Given** an authenticated customer who owns order "ORD-123"
- **And** the order status is "Pending"
- **When** the customer sends a POST request to `/api/v1/orders/ORD-123/cancel`
- **Then** the order status is updated to "Cancelled"
- **And** the response returns HTTP 200 with the updated order details
- **And** a cancellation notification email is queued for dispatch

**Scenario 2: Cancellation denied for shipped orders (Negative Path)**
- **Given** an authenticated customer who owns order "ORD-456"
- **And** the order status is "Shipped"
- **When** the customer sends a POST request to `/api/v1/orders/ORD-456/cancel`
- **Then** the response returns HTTP 400 Bad Request
- **And** the error code is `"ORDER_ALREADY_PROCESSED"`
- **And** the order status remains "Shipped"

**Scenario 3: Non-owner attempts cancellation (Security/Authorization)**
- **Given** an authenticated user "UserB"
- **And** order "ORD-123" belongs to "UserA"
- **When** "UserB" sends a POST request to `/api/v1/orders/ORD-123/cancel`
- **Then** the response returns HTTP 404 Not Found (or 403 Forbidden per API security policy)
- **And** no state changes are made to the order

**Scenario 4: Idempotency on duplicate cancellation requests (Edge Case)**
- **Given** order "ORD-789" has already been cancelled
- **When** the customer sends a duplicate POST request to `/api/v1/orders/ORD-789/cancel`
- **Then** the response returns HTTP 200 with status "Cancelled" without triggering duplicate refund jobs
```

---

## 5. Definition of Ready (DoR) Checklist

Before an engineer starts implementation, ensure:
- [ ] User story follows the standard `As a... I want... So that...` structure.
- [ ] Business value and customer impact are clear.
- [ ] In-Scope and Out-of-Scope boundaries are explicitly stated.
- [ ] Acceptance criteria include Happy, Negative, and Edge Case scenarios in Gherkin format.
- [ ] External dependencies and database impacts are identified.
- [ ] Story point estimation is agreed upon and does not exceed 8 points.
- [ ] Open questions have been resolved with stakeholders.

---

## 6. Definition of Done (DoD) Checklist

Before marking a story closed:
- [ ] All Gherkin acceptance criteria scenarios have automated test coverage (unit and/or integration).
- [ ] All tests pass in the CI/CD pipeline.
- [ ] Code conforms to style guides, passes linting (`ruff`) and static typing (`mypy`).
- [ ] API documentation/OpenAPI schema reflects changes.
- [ ] Database migrations are backwards-compatible and tested.
- [ ] Independent code review has been performed and all reviewer feedback is resolved.
