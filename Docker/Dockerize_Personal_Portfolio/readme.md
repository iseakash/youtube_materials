# Dockerizing a Personal Portfolio

> 🎥 [Mini Production Architecture with Docker — Nginx, FastAPI, Node.js Walkthrough](https://youtu.be/KURS4oPV-Do?si=jQKm_sdXNJ3btrOP)

Three-tier architecture with **Nginx**, **FastAPI**, and **Node.js** — fully containerized with Docker Compose.

---

## Architecture Overview

```
         Host Port 80
              |
          [ Nginx ]
         /          \
    /api/*           /*
        |              |
   [ Backend ]    [ Frontend ]
    FastAPI        Node.js HTTP
    Port 8000       Port 3000
```

- **Nginx** — Single entry point (port 80), reverse-proxies requests
- **Frontend** — Serves static HTML portfolio with inline React (CDN)
- **Backend** — FastAPI with `POST /contact` endpoint for form submissions
- All three containers communicate over a Docker bridge network

---

## Project Structure

```
Personal_Portfolio/
  docker-compose.yml        # Orchestrates all 3 services
  backend/
    Dockerfile
    main.py                 # FastAPI application
    requirements.txt
  frontend/
    Dockerfile
    package.json
    pages/
      index.js              # Node.js HTTP server
      index.html            # Portfolio HTML (with React CDN)
  nginx/
    Dockerfile
    default.conf            # Reverse-proxy config
```

11 files across 4 directories.

---

## Backend — FastAPI (Python)

| Endpoint | Description |
|----------|-------------|
| `GET /` | `{"message": "Portfolio API is running"}` |
| `GET /health` | `{"status": "healthy"}` |
| `POST /contact` | Accepts `{name, email, message}`, stores in memory, returns thank-you message |

**Key Points:**
- Pydantic `BaseModel` validates incoming JSON automatically
- In-memory list stores contact submissions (demo purposes)
- Runs with **uvicorn** on port 8000
- Health check endpoint used by Docker Compose

---

## Frontend — HTML + React via CDN

- Static portfolio HTML served by a minimal **Node.js HTTP server** (port 3000)
- **React 18** loaded via CDN (no build step, no JSX transpilation needed)
- **Babel Standalone** transpiles JSX in the browser on the fly
- GitHub Projects section renders as static HTML cards
- Contact form built as a React component (`ContactForm`)

### ContactForm Component States

| State | Description |
|-------|-------------|
| Idle | Form visible |
| Loading | "Sending..." |
| Success | Green checkmark |
| Error | Red message |

---

## Nginx — Reverse Proxy

```nginx
server {
    listen 80;

    location /api/ {
        proxy_pass http://backend:8000/;
    }

    location / {
        proxy_pass http://frontend:3000/;
    }
}
```

- Routes `/api/*` → FastAPI backend (port 8000)
- Routes everything else `/*` → Node.js frontend (port 3000)
- Strips `/api` prefix — request to `/api/contact` becomes `/contact` at backend
- Single port exposed to host (80), containers isolated on internal network

---

## Docker Compose — Service Orchestration

Startup order: `backend` → `frontend` → `nginx`

```yaml
services:
  backend:
    build: ./backend
    ports: ["8000:8000"]
    healthcheck: { test: ["CMD", "python", "-c", ...] }

  frontend:
    build: ./frontend
    ports: ["3000:3000"]
    depends_on: { backend: { condition: service_healthy } }
    healthcheck: { test: ["CMD", "curl", "-f", "http://localhost:3000"] }

  nginx:
    build: ./nginx
    ports: ["80:80"]
    depends_on:
      frontend: { condition: service_healthy }
      backend: { condition: service_healthy }
```

---

## Dockerfiles — Building Images

| Service | Base Image | Description |
|---------|-----------|-------------|
| Backend | `python:3.12-slim` | Install fastapi+uvicorn → Copy code → Run on :8000 |
| Frontend | `node:20-alpine` | Install curl → Copy code → Run Node.js on :3000 |
| Nginx | `nginx:stable-alpine` | Replace default config → Run on :80 |

---

## Request Lifecycle — Contact Form Demo

```
User fills form + clicks "Send Message"
                │
                ▼
    Browser POST /api/contact
                │
                ▼
       Nginx (port 80)
    └─ matches location /api/
       └─ proxy_pass http://backend:8000/
                │
                ▼
     FastAPI receives POST /contact
    ├─ Pydantic validates JSON body
    ├─ Appends to contacts_db list
    └─ Returns {"message": "Thanks {name}, we'll be in touch!"}
                │
                ▼
    Browser receives JSON → React sets status="success"
    Renders green checkmark + thank-you message
```

---

## Commands Reference

```bash
# Build and start all services
docker compose up --build

# View backend logs
docker compose logs -f backend

# View frontend logs
docker compose logs -f frontend

# Stop all services
docker compose down

# Rebuild a single service
docker compose build backend

# Check container status
docker compose ps
```

---

## Key Takeaways

1. **Docker Compose** orchestrates multi-service apps with health checks and dependency ordering
2. **Nginx** acts as a single entry point, routing requests to the right backend
3. **FastAPI** provides automatic request validation with Pydantic
4. **React via CDN** enables component-based UI without a build toolchain
5. **End-to-end flow** — browser → Nginx → backend → response → browser proves the full request lifecycle
6. **Separation of concerns** — each service runs in its own container, independently deployable
