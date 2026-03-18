# auth

## Overview
Simple FastAPI header validation middleware. Checks the `X-Server-Token` header against the `SERVER_TOKEN` environment variable. When no token is configured, opens access (useful for local development).

## When Should an Agent Use This Module?
- Protecting endpoints with simple bearer token validation
- Checking whether a request is authenticated
- Building token-based access control for API routes

## Key API
| Symbol | Type | Purpose | Agent Instruction |
|--------|------|---------|------------------|
| `require_token(x_server_token)` | function | FastAPI dependency for header validation | Use as a FastAPI path dependency: `Depends(require_token)` |

## Critical Gotchas & Pitfalls for Agents
• **No token configured?** The middleware silently passes when `SERVER_TOKEN` is empty — perfect for local dev, but production deployments must set this env var explicitly.
• **Token mismatch:** Raises `HTTPException(403)` — FastAPI will return a 403 Forbidden with detail="Invalid token".

## Architecture
This module is **minimal by design**. It enforces one rule:
- If `SERVER_TOKEN` is set: request must include a matching `X-Server-Token` header.
- If `SERVER_TOKEN` is empty: all requests are allowed (local-only mode).

No state, no caching, no token expiration.

## Agent Guidance
**Primary Workflow**
1. Include `from src.auth import require_token` in your endpoint file
2. Add `Depends(require_token)` to any route that needs token validation
3. Ensure `.env` or `.env.local` sets `SERVER_TOKEN` before deployment

**Best Practices & Anti-Patterns**
- Always use `Depends()` — FastAPI will call the function automatically and stop if validation fails
- Never modify token logic in endpoints — keep all auth centralized here
- Test both with and without `SERVER_TOKEN` set to catch config drift

**Cross-Module Dependencies**
- Depends on: `fastapi` (FastAPI framework)
- Used by: `endpoints/` (all authenticated routes)

## Progressive Disclosure
**Read this main file by default.**

**Load deeper files ONLY when:**
- You need to understand FastAPI dependency injection: read FastAPI docs on `Depends()`
- You need to audit token handling: read `/docs/ref/ops.md` section on environment configuration
