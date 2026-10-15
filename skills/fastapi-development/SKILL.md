---
name: fastapi-development
description: Comprehensive guide and best practices for building production-grade FastAPI applications in Python. Use whenever designing, implementing, refactoring, or reviewing FastAPI APIs, APIRouters, Pydantic v2 schemas, dependency injection (Depends), async database integration (SQLAlchemy/SQLModel), middleware, error handling, authentication/authorization, and application lifecycle.
---

# FastAPI Production Development Guide

FastAPI is a modern, high-performance web framework for building APIs with Python 3.10+ based on standard Python type hints and Starlette/Pydantic. This skill provides the architectural blueprints, patterns, and strict rules necessary to build maintainable, performant, and secure FastAPI services.

---

## 1. Project Architecture & Directory Layout

Follow a modular, layered architecture that strictly separates transport (HTTP/Routers), business logic (Services), data access (Repositories/Models), and data contracts (Schemas).

```text
src/
├── core/
│   ├── config.py           # Pydantic Settings (.env loading)
│   ├── database.py         # Async engine & session factory
│   ├── security.py         # Passwords, JWT, hashing
│   └── exceptions.py       # Domain-specific base exceptions
├── api/
│   ├── dependencies.py     # Shared route dependencies (get_db, get_current_user)
│   ├── middleware.py       # CORS, Request ID, Logging middleware
│   └── v1/
│       ├── api_router.py   # Aggregates sub-routers
│       └── endpoints/
│           ├── auth.py
│           ├── users.py
│           └── items.py
├── schemas/                # Pydantic v2 request/response models
│   ├── user.py
│   └── item.py
├── services/               # Pure business logic (framework-agnostic)
│   ├── user_service.py
│   └── item_service.py
├── repositories/           # Database queries & persistence
│   ├── user_repo.py
│   └── item_repo.py
├── models/                 # SQLAlchemy ORM / SQLModel entities
│   ├── user.py
│   └── item.py
└── main.py                 # Application factory and lifespan setup
```

---

## 2. Pydantic v2 Schemas & Data Validation

Always decouple database models from public API contracts.

### Rules for Schemas
1. **Never return raw ORM models directly**: Always serialize through an explicit Pydantic response schema with `ConfigDict(from_attributes=True)`.
2. **Distinct Input vs Output Schemas**: Create separate schemas for Create, Update, and Read operations (e.g., `ItemCreate`, `ItemUpdate`, `ItemResponse`).
3. **Use Pydantic v2 Syntax**:
   - Use `model_config = ConfigDict(...)` instead of the legacy `class Config`.
   - Use `@field_validator` and `@model_validator` instead of `@validator` and `@root_validator`.
   - Use `Field(..., min_length=..., ge=...)` for declarative constraints.

```python
from datetime import datetime
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

class UserBase(BaseModel):
    email: EmailStr
    full_name: str = Field(..., min_length=1, max_length=100)

class UserCreate(UserBase):
    password: str = Field(..., min_length=8, max_length=128)

    @field_validator("password")
    @classmethod
    def validate_password_complexity(cls, v: str) -> str:
        if not any(c.isupper() for c in v) or not any(c.isdigit() for c in v):
            raise ValueError("Password must contain at least one uppercase letter and one digit")
        return v

class UserUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=1, max_length=100)
    email: EmailStr | None = None

class UserResponse(UserBase):
    id: int
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
```

---

## 3. Concurrency: `async def` vs `def`

Understanding how FastAPI executes route functions is critical to prevent application freezing.

| Route Signature | Execution Mechanism | When to Use |
| :--- | :--- | :--- |
| `async def` | Runs directly on the **Main Event Loop** | When using non-blocking, async-native libraries (`await session.execute()`, `await httpx_client.get()`). |
| `def` (sync) | Offloaded to an external **Threadpool** (`anyio` worker thread) | When using blocking sync libraries (`requests`, standard file I/O, CPU-intensive tasks, sync DB drivers). |

### ⛔ Critical Anti-Pattern: Blocking the Event Loop
```python
# BAD: Freezes the entire server for all concurrent users!
@router.get("/bad-endpoint")
async def bad_endpoint():
    time.sleep(5)              # NEVER use synchronous blocking I/O in async def!
    response = requests.get(...)# NEVER use requests inside async def!
    return {"status": "ok"}

# GOOD: Non-blocking async I/O
@router.get("/good-endpoint")
async def good_endpoint(client: httpx.AsyncClient = Depends(get_http_client)):
    await asyncio.sleep(5)
    response = await client.get(...)
    return response.json()

# GOOD: Sync endpoint correctly offloaded to worker threadpool
@router.get("/sync-endpoint")
def sync_endpoint():
    time.sleep(5)              # Safe: Runs in a background threadpool
    return {"status": "ok"}
```

---

## 4. Dependency Injection (`Depends`)

FastAPI's dependency injection system enables clean separation of concerns, resource lifecycle management, and seamless test mocking.

### Database Session Lifecycle Dependency
Use `yield` within an async generator to ensure database sessions are reliably committed or rolled back and closed after request completion:

```python
from collections.abc import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

engine = create_async_engine(settings.DATABASE_URL, pool_pre_ping=True, pool_size=10, max_overflow=20)
AsyncSessionFactory = async_sessionmaker(engine, autoflush=False, expire_on_commit=False)

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionFactory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
```

### Composable Authentication Dependency
```python
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")

async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db)
) -> User:
    user_id = decode_access_token(token)
    user = await user_repo.get_by_id(db, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user

async def get_current_active_admin(
    current_user: User = Depends(get_current_user)
) -> User:
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions"
        )
    return current_user
```

---

## 5. Router Organization & Versioning

Structure routers cleanly with explicit prefixes, tags, and standard HTTP response status codes.

```python
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/items", tags=["Items"])

@router.post(
    "",
    response_model=ItemResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create new item"
)
async def create_item(
    payload: ItemCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return await item_service.create_item(db=db, item_in=payload, owner_id=current_user.id)

@router.get(
    "/{item_id}",
    response_model=ItemResponse,
    status_code=status.HTTP_200_OK,
    summary="Retrieve item by ID"
)
async def get_item(
    item_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    item = await item_service.get_item_by_id(db=db, item_id=item_id, owner_id=current_user.id)
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found")
    return item
```

---

## 6. Centralized Error Handling

Do not scatter raw HTTP exceptions with arbitrary error payload shapes across your business logic. Use custom domain exceptions and catch them globally.

```python
# src/core/exceptions.py
class AppException(Exception):
    def __init__(self, message: str, code: str = "BAD_REQUEST", status_code: int = 400):
        self.message = message
        self.code = code
        self.status_code = status_code

class EntityNotFoundError(AppException):
    def __init__(self, entity_name: str, identifier: str | int):
        super().__init__(
            message=f"{entity_name} with identifier '{identifier}' was not found",
            code="NOT_FOUND",
            status_code=404
        )

# In main.py: Register global exception handler
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppException)
    async def app_exception_handler(request: Request, exc: AppException):
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": {
                    "code": exc.code,
                    "message": exc.message,
                    "path": request.url.path
                }
            }
        )
```

---

## 7. Application Lifespan & Clean Startup/Shutdown

Manage persistent connections (e.g., Redis, DB engine, HTTP connection pools) using the modern `@asynccontextmanager` lifespan protocol:

```python
from contextlib import asynccontextmanager
from fastapi import FastAPI

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Initialize connection pools, load ML models, verify DB connectivity
    await database.init_db()
    http_client = httpx.AsyncClient(timeout=10.0)
    app.state.http_client = http_client
    yield
    # Shutdown: Cleanly close pools and client sessions
    await http_client.aclose()
    await database.close_db()

app = FastAPI(title="Core API", lifespan=lifespan)
```

---

## 8. FastAPI Production Checklist

When implementing or reviewing FastAPI code, verify:
- [ ] Are route handler signatures accurately matched to work type (`async def` for async I/O, `def` for sync/CPU work)?
- [ ] Are Pydantic schemas using v2 idioms (`model_config = ConfigDict(from_attributes=True)`)?
- [ ] Are all database sessions scoped to request lifecycle via `Depends` and closed in `finally`?
- [ ] Are relationships loaded eagerly (`selectinload`) when needed to avoid async SQLAlchemy MissingGreenlet exceptions?
- [ ] Are status codes explicit (e.g. `201` for POST creation, `204` for DELETE, `200` for OK)?
- [ ] Are secret keys, DB credentials, and sensitive configurations strictly managed through `pydantic-settings` BaseSettings reading from environment variables?
- [ ] Is CORS configured with explicit allowed origins rather than `allow_origins=["*"]` when credentials (`allow_credentials=True`) are enabled?
