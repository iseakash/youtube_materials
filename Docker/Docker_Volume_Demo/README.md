# Docker Volumes & Persistence Demo

> **Objective:** Show how Docker volumes enable permanent data storage across container lifecycles.
>
> **Stack:** MySQL 8 + Flask (Python)

---

## Slide 1 — The Problem

**Containers are ephemeral by design.**

When a container is removed, everything inside it — including database records — is destroyed.

```bash
# Data exists only inside the container's writable layer
docker compose up -d
# ... add data ...
docker compose down
# Data is gone forever
```

**Question:** How do we keep data safe when containers come and go?

---

## Slide 2 — Solution: Docker Volumes

A **volume** is persistent storage managed by Docker, stored on the host filesystem.

```
┌─────────────────────────────────────┐
│         Host Filesystem             │
│  ┌───────────────────────────────┐  │
│  │    Volume (sales_data)        │  │
│  │  /var/lib/docker/volumes/     │  │
│  └──────────┬────────────────────┘  │
│             │ mount                 │
│  ┌──────────▼────────────────────┐  │
│  │     Container (MySQL)         │  │
│  │  /var/lib/mysql ← volume      │  │
│  └───────────────────────────────┘  │
└─────────────────────────────────────┘
```

**Key idea:** The volume lives **outside** the container, so it survives container deletion.

---

## Slide 3 — Project Overview

```
docker-volume-demo/
├── app/
│   ├── app.py              # Flask backend — CRUD API for sales records
│   ├── Dockerfile           # Builds the Python container
│   ├── requirements.txt     # flask, mysql-connector-python
│   └── templates/
│       └── index.html       # Sales dashboard UI
├── docker-compose.yml       # Defines db + app services
└── README.md
```

Two services:
- **`db`** — MySQL 8, listens on port 3306
- **`app`** — Flask app, listens on port 5000

---

## Slide 4 — docker-compose.yml (Annotated)

```yaml
services:
  db:
    image: mysql:8
    environment:
      MYSQL_ROOT_PASSWORD: rootpassword
      MYSQL_DATABASE: sales_db
    ports:
      - "3306:3306"
    # --- STEP 2: Uncomment these for persistence ---
    # volumes:
    #   - sales_data:/var/lib/mysql

  app:
    build: ./app
    ports:
      - "5000:5000"
    environment:
      DB_HOST: db
      DB_USER: root
      DB_PASSWORD: rootpassword
      DB_NAME: sales_db
    depends_on:
      - db

# --- STEP 2: Uncomment this too ---
volumes:
  sales_data:
```

Key detail: Named volumes must be declared at the **top-level** `volumes:` key in Compose.

---

## Slide 5 — DEMO: Part 1 — WITHOUT Volumes ❌

Data stored inside the **container's ephemeral layer** — lost on deletion.

### Step-by-Step

| # | Action | Command |
|---|--------|---------|
| 1 | Start stack | `docker compose up -d` |
| 2 | Open app at `http://localhost:5000` | — |
| 3 | Add 2–3 sales records via the UI | — |
| 4 | Check data persists (refresh page) | — |
| 5 | Tear everything down | `docker compose down` |
| 6 | Restart stack | `docker compose up -d` |
| 7 | **Observe: Data is gone** | Empty table |

> **Why?** `docker compose down` removes containers. Without a volume mount, MySQL's `/var/lib/mysql` is inside the container and gets destroyed with it.

---

## Slide 6 — DEMO: Part 2 — WITH Volumes ✅

Data stored in a **named volume** — survives container recreation.

### Enable the Volume

Edit `docker-compose.yml`: uncomment lines 10–11 and line 27.

```yaml
services:
  db:
    ...
    volumes:                       # ← uncommented
      - sales_data:/var/lib/mysql  # ← uncommented

volumes:
  sales_data:                      # ← uncommented
```

### Step-by-Step

| # | Action | Command |
|---|--------|---------|
| 1 | Start stack | `docker compose up -d` |
| 2 | Open app at `http://localhost:5000` | — |
| 3 | Add 2–3 sales records via the UI | — |
| 4 | Tear everything down | `docker compose down` |
| 5 | Restart stack | `docker compose up -d` |
| 6 | **Observe: Data is still there** | Full table restored |

> **Why?** The volume `sales_data` is mounted at `/var/lib/mysql`. When MySQL writes data, it goes to the **host** filesystem, not the container. Deleting the container leaves the volume untouched.

---

## Slide 7 — Volume Management Commands

```bash
# List all volumes on the system
docker volume ls

# Inspect a specific volume (shows driver, mountpoint, labels)
docker volume inspect docker-volume-demo_sales_data

# Output:
# {
#   "Name": "docker-volume-demo_sales_data",
#   "Driver": "local",
#   "Mountpoint": "/var/lib/docker/volumes/docker-volume-demo_sales_data/_data",
#   "CreatedAt": "2026-06-12T12:00:00Z"
# }

# Remove a specific volume (only if no container uses it)
docker volume rm docker-volume-demo_sales_data

# Remove all unused volumes (cleanup)
docker volume prune
```

---

## Slide 8 — Deep Dive: How Volumes Work

```
                     Container Lifecycle
    ┌─────────────────────────────────────────────────────┐
    │                                                     │
    │   docker compose up     docker compose down          │
    │         │                       │                   │
    │         ▼                       ▼                   │
    │  ┌──────────────┐       ┌──────────────┐            │
    │  │  Container   │ ───►  │  Container   │            │
    │  │  (created)   │       │  (removed)   │            │
    │  └──────┬───────┘       └──────────────┘            │
    │         │                                           │
    │         │ mount                                     │
    │         ▼                                           │
    │  ┌──────────────┐                                   │
    │  │  Volume      │  ◄──── SURVIVES!                  │
    │  │  (persist)   │                                   │
    │  └──────────────┘                                   │
    │                                                     │
    └─────────────────────────────────────────────────────┘
```

### Volume vs Bind Mount vs tmpfs

| Feature | Named Volume | Bind Mount | tmpfs |
|---------|-------------|------------|-------|
| Managed by Docker | ✅ Yes | ❌ No | ✅ Yes |
| Persists after container delete | ✅ Yes | ✅ Yes | ❌ No |
| Stored in | `/var/lib/docker/volumes/` | Any host path | RAM |
| Backup / restore | Easy | Manual | N/A |
| Use case | Persistent DB data | Dev config files | Temp secrets |

---

## Slide 9 — Key Takeaways

| Concept | Summary |
|---------|---------|
| **Containers are ephemeral** | Data inside a container dies with it |
| **Volumes are persistent** | Data in a volume survives container deletion |
| **Named volumes** | Docker-managed; declared in `docker-compose.yml` under `volumes:` at top level |
| **Mount path** | Volume must be mounted at the database's data directory (MySQL → `/var/lib/mysql`) |
| **Volume lifecycle** | Created on `up`, persists through `down`, removed only via `down -v` or explicit `volume rm` |

### Quick Comparison

```
┌───────────────────┬────────────────────┬────────────────────┐
│                   │  WITHOUT Volume    │   WITH Volume      │
├───────────────────┼────────────────────┼────────────────────┤
│ Add data          │ ✅ Saved           │ ✅ Saved           │
│ docker compose down│ ❌ Lost           │ ✅ Survives        │
│ docker compose up │ ❌ Table empty     │ ✅ Data restored   │
└───────────────────┴────────────────────┴────────────────────┘
```

---

## Slide 10 — Cleaning Up

```bash
# Stop containers (keeps volumes)
docker compose down

# Stop containers AND delete the named volume
docker compose down -v

# Verify volume is gone
docker volume ls
```
