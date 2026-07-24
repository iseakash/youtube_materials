# FastAPI Security — 20 Real-World API Security Implementations

A hands-on portfolio of **20 production-grade FastAPI tasks** covering the full spectrum of API security — from input validation and role-based access to rate limiting, CORS, multi-tenancy, webhooks, audit logging, and a complete LMS.

## What's Inside

| Layer | What I Built |
|-------|-------------|
| **Validation** | Pydantic models with `EmailStr`, `Field` constraints, enums, duplicate detection |
| **Authentication** | API key auth (`APIKeyHeader` + `Security`/`Depends`), token-based auth (`secrets.token_urlsafe`) |
| **Authorization** | Role-based guards (student / instructor / admin), 401 vs 403 distinction |
| **Rate Limiting** | slowapi per-IP, custom per-key sliding-window tracker |
| **CORS** | Exact-origin whitelisting, method/header restriction |
| **Multi-Tenancy** | Org-scoped data isolation, cross-tenant leakage prevention |
| **Webhooks** | Replay attack prevention via idempotent `event_id` tracking |
| **Audit Logging** | Immutable append-only logs with automatic sensitive-field redaction |
| **File Upload** | Type/size validation, UUID-based safe storage |
| **Complete LMS** | 10-endpoint system with 3 roles, enrollments, seat limits, audit trail |

## Key Files

| File | Purpose |
|------|---------|
| [`master_api_code.py`](./master_api_code.py) | Consolidated reference: all patterns in one runnable file (3 sections: Basics → CRUD → Security) |
| [`Usecases/`](./Usecases/) | 20 individual task folders, each with its own `main.py`, `.env`, and `README.md` |
| [`Usecases/README.md`](./Usecases/README.md) | Full task specification document (scenarios, requirements, security challenges) |

## The Impact

This repository is **not** a tutorial — it's a **reference-grade implementation library** that demonstrates:

- **Deep security thinking**: every endpoint has a threat model behind it
- **Code consistency**: all 20 tasks follow identical patterns — single import style, uniform error handling, same scaffolding
- **Real-world readiness**: the patterns here mirror what production APIs at scale need (tenant isolation, audit trails, idempotent webhooks, role guards)

It serves as both a **portfolio anchor** for API security roles and a **copy-paste reference** for building secure FastAPI applications from day one.

> *"Security is not a feature — it's a way of writing code."*
