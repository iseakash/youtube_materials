# Docker Mini Project — YouTube Materials

This repository contains **three Docker-based projects** that progressively explore containerization concepts, from basic data persistence to full-stack multi-container orchestration.

---

## 1. Docker_Volume_Demo — Beginner

**Concepts explored:** Named volumes, ephemeral vs persistent storage, service dependencies, environment variables.

A **2-container app** (Flask + MySQL) demonstrating the core Docker volume workflow. The app is a sales tracker that highlights data loss without volumes (`docker compose down` destroys DB data) and data persistence once a named volume is mounted at MySQL's data directory.

```
Browser → Flask (port 5000) → MySQL (port 3306)
```

---

## 2. Dockerize_Personal_Portfolio — Intermediate

**Concepts explored:** Multi-service orchestration (3 containers), reverse proxy (Nginx), health checks, dependency ordering, separation of concerns.

A **3-tier personal portfolio** with Nginx as the single entry point, a Node.js static frontend, and a FastAPI backend (contact form). Nginx routes `/api/*` to the backend and `/*` to the frontend, with health check conditions ensuring correct startup order.

```
Browser → Nginx (port 80) → /api/* → FastAPI (8000)
                          → /*     → Node.js Frontend (3000)
```

---

## 3. Multi_Container_Employee_Management_System — Advanced

**Concepts explored:** Full CRUD across 4 containers, custom bridge network, named volume for DB persistence, health-checked dependency chains, environment files, CORS, `restart: unless-stopped`.

A **full-stack Employee Management System** with Nginx reverse proxy, Next.js frontend, FastAPI REST API, and PostgreSQL. All containers communicate over an explicit custom bridge network (`ems-network`). The backend uses parameterized SQL queries, and the entire stack boots with a single `docker compose up --build`.

```
Browser → Nginx (port 80) → /api/* → FastAPI (5000) → PostgreSQL (5432)
                          → /*     → Next.js (3000)
```
