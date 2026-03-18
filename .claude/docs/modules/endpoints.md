# endpoints

## Overview
FastAPI route directory containing auth logic. Actual HTTP endpoints are defined in `main.py` (not in sub-routers). The `endpoints/` directory provides token validation helpers used by the main FastAPI app.

## When Should an Agent Use This Module?
- Understanding token validation and auth flow
- Adding new authentication endpoints
- Debugging authorization failures

## Key API
| Symbol | Type | Purpose | Agent Instruction |
|--------|------|---------|------------------|
| `src/endpoints/auth.py` | module | Token validation, JWT decoding | Import `validate_token` for auth dependency |
| `validate_token(credentials)` | function | Validate incoming X-Authorization header | Use as FastAPI `Depends()` |

### Route Organization
**Important:** HTTP endpoints are **not** organized in sub-router files. All routes are defined directly in `main.py`:
- `/health` — health check
- `/admin/*` — admin operations (rebuild index, etc.)
- `/data/*` — public data (systems, gate graph)
- `/ship-profile` — ship profile get/set
- `/log/ingest` — log event ingestion
- `/chat/*` — chat endpoints (auth'd)
- `/structure/*` — structure operations

## Critical Gotchas & Pitfalls for Agents
• **No sub-router files:** Do not expect `ship_ai.py`, `structure_ai.py`, `data.py`, or `admin.py` — they don't exist. All routes in `main.py`.
• **Token validation in auth.py:** The `validate_token()` helper is in `endpoints/auth.py` and is imported by `main.py`.
• **Dependency injection:** Use `Depends(require_token)` in main.py to protect endpoints (not Depends(validate_token)).

## Architecture
```
main.py imports:
  from src.endpoints.auth import validate_token, auth_router
  app.include_router(auth_router)
  ↓
Request arrives at FastAPI endpoint in main.py
  ↓
Dependency: Depends(require_token) validates X-Server-Token
  ↓
Route handler processes request, calls core logic
  ↓
Response: JSON or StreamingResponse
```

## Agent Guidance
**Primary Workflow**
1. To add a new endpoint: edit `main.py` directly (not a sub-router file)
2. For token auth: add `dependencies=[Depends(require_token)]` to the @app route
3. For token validation details: check `src/endpoints/auth.py`

**Best Practices & Anti-Patterns**
- Always / Define routes in `main.py`, not separate files
- Always / Use `require_token` dependency for protected endpoints
- Never / Look for non-existent sub-router files (ship_ai.py, structure_ai.py, etc.)

**Cross-Module Dependencies**
- Depends on: `fastapi`, `auth` (token validation)
- Used by: `main.py` (app registration)

## Progressive Disclosure
**Read this main file by default.**

**Load deeper files ONLY when:**
- You need to understand token validation: read `src/endpoints/auth.py`
- You need to add a new endpoint: read `main.py` for pattern
- You need request/response schemas: read `/docs/CODEBASE.md` section on API Endpoints
