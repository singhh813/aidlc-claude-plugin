---
name: software-testing
description: Comprehensive testing guide for Python and FastAPI applications. Use whenever writing, planning, debugging, or reviewing automated tests, including pytest fixtures, async HTTP client testing (httpx.AsyncClient), FastAPI dependency overrides, database isolation and rollback fixtures, mock strategies, parametrized edge cases, and test pyramid strategies (unit, integration, e2e).
---

# Software Testing & QA Best Practices

Writing reliable, maintainable, and fast automated tests is essential for robust software delivery. This skill defines modern testing strategies for Python and FastAPI services using `pytest`, `pytest-asyncio`, `httpx`, and `SQLAlchemy`.

---

## 1. Testing Pyramid & Boundaries

Maintain a balanced distribution across test tiers:

```
        / \
       /   \        End-to-End (E2E) (5-10%)
      /     \       - Test entire system through public HTTP endpoints
     /-------\      - Real database, real network/service boundaries
    /         \     
   /           \    Integration Tests (20-30%)
  /             \   - Multiple units working together (Routers + DB + Service)
 /---------------\  - Real database in transaction rollback, mocked external APIs
/                 \ 
/                   \ Unit Tests (60-70%)
/---------------------\ - Single function, class, or service in isolation
                         - Fast execution (milliseconds), external I/O mocked
```

---

## 2. Pytest Configuration & Fixture Lifecycle

Structure test suites cleanly using root and directory-level `conftest.py` files.

### Pytest Configuration (`pyproject.toml`)
```toml
[tool.pytest.ini_options]
minversion = "8.0"
addopts = "-ra -q --strict-markers --strict-config"
asyncio_mode = "auto"
testpaths = ["tests"]
python_files = ["test_*.py"]
python_functions = ["test_*"]
markers = [
    "unit: Fast, isolated unit tests",
    "integration: Tests interacting with database or multiple subsystems",
    "slow: Tests that take more than 1 second to run",
]
```

### Fixture Scoping & Cleanup Rules
- Use `scope="session"` for expensive, immutable setup (e.g. database schema migrations, test engine creation).
- Use `scope="function"` (default) for stateful resources (database sessions, HTTP clients, mocked state).
- Always use the `yield` statement for fixtures requiring teardown:

```python
# tests/conftest.py
import pytest
from collections.abc import AsyncGenerator

@pytest.fixture(scope="function")
async def temp_resource() -> AsyncGenerator[Resource, None]:
    # Setup phase
    resource = await create_resource()
    yield resource
    # Teardown phase (guaranteed execution even if test fails)
    await resource.cleanup()
```

---

## 3. Testing FastAPI Applications

Test API endpoints using `httpx.AsyncClient` with Starlette's `ASGITransport`. This allows direct, in-memory async testing of the ASGI application without spawning an actual HTTP network listener.

### Base Test Fixtures (`tests/conftest.py`)
```python
import pytest
from collections.abc import AsyncGenerator
from httpx import ASGITransport, AsyncClient
from src.main import app

@pytest.fixture(scope="function")
async def client() -> AsyncGenerator[AsyncClient, None]:
    """In-memory async client for testing FastAPI endpoints."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
```

### Overriding Dependencies with `app.dependency_overrides`
FastAPI provides `app.dependency_overrides` to swap out production dependencies (auth, database, external services) cleanly during tests:

```python
import pytest
from src.main import app
from src.api.dependencies import get_current_user, get_db
from src.models.user import User

@pytest.fixture(scope="function")
def mock_authenticated_user(client: AsyncClient):
    """Overrides authentication dependency with a test user."""
    fake_user = User(id=1, email="tester@example.com", is_superuser=False)
    
    app.dependency_overrides[get_current_user] = lambda: fake_user
    yield fake_user
    app.dependency_overrides.pop(get_current_user, None)
```

### Example Endpoint Test
```python
import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_create_item_success(client: AsyncClient, mock_authenticated_user):
    payload = {"name": "Test Item", "price": 49.99}
    response = await client.post("/api/v1/items", json=payload)
    
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Test Item"
    assert data["price"] == 49.99
    assert "id" in data

@pytest.mark.asyncio
async def test_create_item_validation_error(client: AsyncClient, mock_authenticated_user):
    # Missing required 'name' field
    payload = {"price": 49.99}
    response = await client.post("/api/v1/items", json=payload)
    
    assert response.status_code == 422
    assert "detail" in response.json()
```

---

## 4. Database Isolation with Transactional Rollbacks

Never let tests persist state into each other. Use a nested transaction (savepoint) rollback pattern so each test starts with an empty/clean database state and rolls back automatically upon completion.

```python
import pytest
from collections.abc import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from src.main import app
from src.api.dependencies import get_db
from src.models.base import Base

TEST_DATABASE_URL = "postgresql+asyncpg://postgres:postgres@localhost:5432/test_db"
test_engine = create_async_engine(TEST_DATABASE_URL)
TestSessionLocal = async_sessionmaker(test_engine, expire_on_commit=False)

@pytest.fixture(scope="session", autouse=True)
async def prepare_test_db():
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await test_engine.dispose()

@pytest.fixture(scope="function")
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Runs each test in an isolated transaction that rolls back at completion."""
    async with test_engine.connect() as connection:
        transaction = await connection.begin()
        session = AsyncSession(bind=connection, expire_on_commit=False)
        
        # Override the FastAPI route dependency
        app.dependency_overrides[get_db] = lambda: session
        
        yield session
        
        app.dependency_overrides.pop(get_db, None)
        await session.close()
        await transaction.rollback()
```

---

## 5. Mocking Strategies & External Services

### Safe Mocking Rules
1. **Mock at system boundaries**: Mock third-party APIs (Stripe, Twilio, SendGrid), message queues, and external webhooks. Do not mock internal business logic or data structures unless strictly necessary.
2. **Never mock what you do not own without specs**: Use `spec=TargetClass` or `autospec=True` to ensure mocked methods actually exist on the target class.
3. **Mocking External HTTP Requests**: Use `respx` to intercept HTTP calls rather than patching raw `httpx.get` or `aiohttp` methods:

```python
import pytest
import respx
from httpx import Response

@pytest.mark.asyncio
@respx.mock
async def test_payment_processing(client: AsyncClient, mock_authenticated_user):
    # Intercept outgoing Stripe charge request
    stripe_route = respx.post("https://api.stripe.com/v1/charges").mock(
        return_value=Response(200, json={"id": "ch_123", "status": "succeeded"})
    )
    
    response = await client.post("/api/v1/orders/1/pay")
    assert response.status_code == 200
    assert stripe_route.called
```

---

## 6. Parametrized Testing & Edge Cases

Use `@pytest.mark.parametrize` to systematically test boundary conditions, authorization rules, and edge cases with minimal code duplication.

```python
import pytest

@pytest.mark.parametrize(
    "payload, expected_status, error_field",
    [
        ({"email": "not-an-email", "full_name": "Bob"}, 422, "email"),
        ({"email": "bob@example.com", "full_name": ""}, 422, "full_name"),
        ({"email": "bob@example.com"}, 422, "full_name"),
    ],
    ids=["invalid_email_format", "empty_name", "missing_required_field"]
)
@pytest.mark.asyncio
async def test_user_creation_validation_edges(
    client: AsyncClient, payload: dict, expected_status: int, error_field: str
):
    response = await client.post("/api/v1/users", json=payload)
    assert response.status_code == expected_status
    errors = response.json()["detail"]
    assert any(error_field in e["loc"] for e in errors)
```

---

## 7. Testing Anti-Patterns to Avoid

| Anti-Pattern | Why it is Dangerous | Remediation |
| :--- | :--- | :--- |
| **`time.sleep()` in tests** | Causes non-deterministic flakiness and slows test suite. | Use async event polling, wait conditions, or explicit mocks. |
| **Database state leakage** | Test A creates data that causes Test B to fail if run in different order. | Use transactional rollback fixtures per test. |
| **Mocking everything** | Tests pass 100% in CI but app fails in production due to broken contracts. | Test real database and real router bindings in integration tests. |
| **Asserting only status codes** | `assert res.status_code == 200` passes even if payload is corrupt or empty. | Always assert on response payload structure, keys, and values. |
| **Tests without negative cases** | Missing edge case validation allows regressions in error handlers. | Test 400, 401, 403, 404, 409, and 422 responses explicitly. |

---

## 8. Automated Testing Checklist

Before marking any testing task complete:
- [ ] Are all new and modified endpoints covered by integration tests?
- [ ] Does each test run independently without relying on execution order (`pytest-random-order`)?
- [ ] Are database fixtures properly wrapped in transactional rollbacks?
- [ ] Are third-party network calls completely mocked using `respx` or equivalent?
- [ ] Are happy paths, boundary inputs, and validation failure paths explicitly asserted?
- [ ] Have you verified the test suite passes cleanly: `pytest tests/ -v`?
- [ ] Have linting and type checks passed: `ruff check` and `mypy`?
