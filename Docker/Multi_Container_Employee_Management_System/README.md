# Build a Multi-Container Employee Management System Using Docker Compose

---

## Slide 1: What We Built

- **4 Docker containers** working together as one application
- **Frontend** (Next.js + React) — User interface to manage employees
- **Backend** (FastAPI + Python) — REST API for CRUD operations
- **Database** (PostgreSQL) — Stores employee records permanently
- **Nginx** — Reverse proxy that routes traffic to the right place
- **Full CRUD** — Create, Read, Update, Delete employees from the browser

---

## Slide 2: Project Folder Structure

```
Docker_Mini_Project/
├── .env                         # DB credentials (admin, admin123)
├── docker-compose.yml           # Orchestrates all 4 services
├── README.md                    # This file
│
├── backend/                     # FastAPI Python backend
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── config.py                # Reads DB_HOST, DB_USER, etc. from env
│   └── app.py                   # REST API with all 5 endpoints
│
├── frontend/                    # Next.js React frontend
│   ├── Dockerfile
│   ├── package.json
│   ├── next.config.js
│   └── pages/
│       └── index.js             # Full React component with hooks
│
└── nginx/                       # Nginx reverse proxy
    ├── Dockerfile
    └── default.conf             # Routes / → frontend, /api/ → backend
```

---

## Slide 3: Architecture Overview

```
     User → http://localhost (Port 80)
                │
          ┌─────┴──────┐
          │   NGINX    │  ← Receptionist: directs traffic
          │ Proxy      │
          └─────┬──────┘
                │
        ┌───────┴───────────┐
        │                   │
   / → Frontend       /api/ → Backend
   Port 3000               Port 5000
   (Next.js UI)            (FastAPI API)
        │                   │
        │              ┌────┴─────┐
        │              │PostgreSQL│
        │              │ Port 5432│
        │              └──────────┘
   Browser makes
   API calls via
   http://localhost:5000
```

---

## Slide 4: Services Deep Dive

### Frontend (Next.js + React)

| Aspect | Details |
|--------|---------|
| **Role** | Serves the Employee Management UI |
| **Port** | `3000` |
| **Start** | `npm run dev` (Next.js dev server) |
| **Tech** | React with `useState`, `useEffect`, `useCallback` hooks |
| **API calls** | `fetch()` to `http://localhost:5000/api/employees` |
| **Key file** | `frontend/pages/index.js` — single page component with full CRUD UI |

**What it does:** Displays a table of employees, a form to add new ones, and edit/delete buttons. All data comes from the backend API.

---

### Backend (FastAPI + Python)

| Aspect | Details |
|--------|---------|
| **Role** | REST API handling all data operations |
| **Port** | `5000` |
| **Start** | `uvicorn app:app --host 0.0.0.0 --port 5000` |
| **Framework** | FastAPI with CORS middleware |
| **Database** | PostgreSQL via psycopg2 |

**API Endpoints:**

| Method | Route | Action |
|--------|-------|--------|
| `GET` | `/api/employees` | List all employees |
| `GET` | `/api/employees/{id}` | Get one employee |
| `POST` | `/api/employees` | Create new employee |
| `PUT` | `/api/employees/{id}` | Update employee |
| `DELETE` | `/api/employees/{id}` | Delete employee |
| `GET` | `/api/health` | Health check |

---

### Nginx (Reverse Proxy)

| Aspect | Details |
|--------|---------|
| **Role** | Entry point — routes traffic to frontend or backend |
| **Port** | `80` (standard HTTP) |
| **Image** | `nginx:alpine` |

**Routing rules:**

```
http://localhost/              → frontend:3000/     (UI page)
http://localhost/api/employees → backend:5000/api/  (API calls)
```

**Why Nginx?** It gives a single entry point (`localhost:80`) instead of having users remember two different ports for frontend and backend.

---

### Database (PostgreSQL)

| Aspect | Details |
|--------|---------|
| **Role** | Persistent data storage |
| **Port** | `5432` |
| **Image** | `postgres:16-alpine` |
| **Volume** | `postgres_data` — data survives container restarts |

**Employees table schema:**

| Column | Type | Notes |
|--------|------|-------|
| `id` | SERIAL | Auto-incremented, primary key |
| `name` | VARCHAR(100) | Required |
| `email` | VARCHAR(100) | Required, unique |
| `department` | VARCHAR(100) | Optional |
| `position` | VARCHAR(100) | Optional |
| `salary` | NUMERIC(10,2) | Optional |
| `created_at` | TIMESTAMP | Auto-set |

---

## Slide 5: Docker Concepts Explained with Analogies

### Dockerfile = Recipe Card
Each Dockerfile is like a recipe — it lists the ingredients (base image), steps (commands), and tells the oven (Docker) how to cook it.

### docker-compose.yml = Restaurant Menu
It lists all the dishes (services) available, their prices (ports), and how they relate to each other (depends_on, networks).

### Multi-Container Networking = Office Phone System
Containers talk to each other by **service name** (like `backend`, `db`) instead of IP addresses. Docker runs an internal DNS — like an office directory — so they always find each other.

### conn vs cursor = Phone Line vs Speaker
> "conn is the phone line to the database. cur is the person speaking on that phone. You need both — conn keeps the line open, cur actually sends queries and gets results."

### commit() = Hitting Save
> "Without commit, your changes exist only in a draft. If the power goes out, they are lost. commit() is like hitting Save — permanently written."

### %s placeholder = The Fence
> "%s acts like a fence between code and data. It tells PostgreSQL: 'Treat whatever comes next as a value, not as SQL commands.' This prevents SQL injection."

### RETURNING * = One-Stop Hotel Check-in
> "Normally INSERT just inserts and returns nothing — like giving your name at a hotel but never getting your room number. RETURNING * hands you the room key immediately."

### CORS = Browser's Security Guard
> "CORS is like telling the browser's security guard: 'It is okay for the frontend website to talk to this backend API. Without this, the browser blocks the request for safety.'"

### Docker Volumes = A Safe
Data inside a container is temporary — like writing on a whiteboard. A volume is like a safe — even if the container is destroyed, the data remains.

### Health Checks = Calling Ahead
The backend checks if PostgreSQL is ready before starting — like calling a restaurant to make sure the kitchen is open before placing an order.

---

## Slide 6: Docker Compose Configuration

```yaml
version: "3.8"

services:
  db:
    image: postgres:16-alpine
    environment:
      POSTGRES_DB: ${DB_NAME}
      POSTGRES_USER: ${DB_USER}
      POSTGRES_PASSWORD: ${DB_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${DB_USER} -d ${DB_NAME}"]
    networks:
      - ems-network

  backend:
    build: ./backend
    environment:
      DB_HOST: db
      DB_NAME: ${DB_NAME}
      DB_USER: ${DB_USER}
      DB_PASSWORD: ${DB_PASSWORD}
    depends_on:
      db:
        condition: service_healthy
    networks:
      - ems-network

  frontend:
    build: ./frontend
    ports:
      - "3000:3000"
    depends_on:
      - backend
    networks:
      - ems-network

  nginx:
    build: ./nginx
    ports:
      - "80:80"
    depends_on:
      - frontend
      - backend
    networks:
      - ems-network

volumes:
  postgres_data:

networks:
  ems-network:
    driver: bridge
```

---

## Slide 7: How to Run

### Prerequisites
- Docker and Docker Compose installed

### Steps

```bash
# 1. Clone or navigate to the project
cd Docker_Mini_Project

# 2. Start all services (build + run)
docker-compose up --build

# 3. Open in your browser
http://localhost
```

### Useful Commands

```bash
# Stop all containers
docker-compose down

# Stop and delete volumes (wipes database data)
docker-compose down -v

# View running containers
docker ps

# View container logs
docker logs employee-backend
docker logs employee-frontend
docker logs employee-nginx
docker logs employee-db

# View Docker resources
docker volume ls
docker network ls
```

---

## Slide 8: How It All Connects

### When you open http://localhost:

```
1. Browser → Nginx (port 80)
2. Nginx → Frontend (port 3000) → Serves React page
3. React page loads → JavaScript runs
4. JS → http://localhost:5000/api/employees → Backend (port 5000)
5. Backend → PostgreSQL (port 5432) → Fetches or saves data
6. Backend → Returns JSON response → Browser displays it
```

### Data flow for "Add Employee":

```
User fills form → clicks "+ Add Employee"
→ POST http://localhost:5000/api/employees (JSON body)
→ Backend validates → INSERT INTO employees ... RETURNING *
→ PostgreSQL saves → Returns new row
→ Backend returns 201 → Browser shows success toast
→ React re-fetches GET /api/employees → Table updates
```

---

## Slide 9: Key Takeaways

| Concept | How This Project Demonstrates It |
|---------|----------------------------------|
| **Dockerfile** | 3 separate Dockerfiles (Node.js, Python, Nginx) |
| **Docker Compose** | 4 services defined in one YAML file |
| **Multi-container networking** | Services communicate via `ems-network` using service names |
| **Reverse proxy** | Nginx routes `/api/*` to backend, `/*` to frontend |
| **Volumes** | `postgres_data` persists database across restarts |
| **Environment variables** | `.env` file feeds credentials to DB and backend |
| **Health checks** | Backend waits for PostgreSQL to be ready |
| **CORS** | Backend allows cross-origin requests from frontend |
| **Parameterized queries** | `%s` placeholders prevent SQL injection |
| **One-command startup** | `docker-compose up --build` starts everything |

---

## Slide 10: What You Learned

✅ Build a full-stack app with 4 Docker containers
✅ Use Docker Compose to orchestrate multi-service applications
✅ Configure Nginx as a reverse proxy
✅ Connect a Python/FastAPI backend to PostgreSQL
✅ Build a React/Next.js frontend
✅ Handle CRUD operations with REST API
✅ Understand CORS, SQL injection prevention, and database transactions
✅ Use Docker volumes for persistent data storage
✅ Debug multi-container applications using logs

---

## Slide 11: Live Demo Commands

```bash
# Terminal 1: Start the project
docker-compose up --build

# After demo, show:
docker ps                    # See all running containers
docker volume ls             # See persistent volume
docker network ls            # See custom network
docker logs employee-db     # See database queries in real-time
```

### Try It Yourself

1. Open http://localhost
2. Add employees using the form
3. Edit employee details
4. Delete employees
5. Refresh the page — data persists!
6. Run `docker-compose down` then `docker-compose up` — data still there (thanks to volumes)

---

## Takeaway

**"One command to start, all services connected, data persisted — that is the power of Docker Compose."**

This project proves that you don't need complex infrastructure to run a full-stack application. With just `docker-compose up --build`, four different technologies (Next.js, FastAPI, PostgreSQL, Nginx) work together seamlessly — each in its own container, communicating over a shared network, with data that survives restarts.

The same pattern scales to production: add more services, swap databases, deploy to the cloud. The fundamentals remain the same.
