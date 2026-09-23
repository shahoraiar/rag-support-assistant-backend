# SupportAI Backend

## About

**SupportAI** is a RAG-based support backend that helps customers get answers from a knowledge base and escalate to human agents when needed.

**What it does:**
- **Auth** — JWT login/register, Google OAuth, password reset
- **Tickets** — create, assign, resolve, SLA tracking, activity timeline
- **AI Chat** — RAG Q&A over uploaded docs (pgvector + OpenRouter), escalate to agent
- **Knowledge base** — PDF/document upload, chunking, embeddings
- **Notifications** — real-time alerts (WebSocket-ready)
- **Analytics** — admin dashboard and agent workload

**Stack:** Django REST Framework · PostgreSQL + pgvector · Redis · OpenRouter · Docker

```bash
docker compose up -d          # background-এ চালু
docker compose logs -f web    # log দেখতে
docker compose down           # বন্ধ করতে
```

---

## Table of Contents

1. [About](#about)
2. [Project Structure](#project-structure)
3. [Run with Docker (Recommended)](#run-with-docker-recommended)
4. [Run Locally (without Docker)](#run-locally-without-docker)
5. [Swagger API Docs](#swagger-api-docs)
6. [Demo Accounts](#demo-accounts)
7. [API Endpoints](#api-endpoints)
8. [Useful Docker Commands](#useful-docker-commands)
9. [Troubleshooting](#troubleshooting)

---

## Project Structure

```
├── supportai/              # Project settings
├── accountssu/             # User (models)
├── ticketssu/              # Ticket, SLA, Activity (models)
├── knowledgesu/            # Knowledge base (models)
├── chatsu/                 # Chat sessions (models)
├── notificationssu/        # Notifications (models)
├── common/                 # Shared helpers, permissions, RAG
├── globalapi/              # Public APIs (auth)
│   ├── serializers/
│   ├── views/
│   └── urls/
├── meapi/                  # Authenticated APIs
│   ├── serializers/
│   ├── views/
│   └── urls/
├── Dockerfile
├── docker-compose.yml
└── entrypoint.sh
```

**Pattern:** Models → separate `*su` apps | API logic → `globalapi` + `meapi`

---

## Run with Docker (Recommended)

> **বাংলায় সংক্ষেপে:** `cp env_sample.txt .env` → `docker compose up --build`  
> তারপর browser-এ খোল: http://localhost:8000/api/docs/

### Prerequisites

- [Docker](https://docs.docker.com/get-docker/) installed
- [Docker Compose](https://docs.docker.com/compose/install/) installed

Verify:

```bash
docker --version
docker compose version
```

### Step 1 — Create `.env` file

```bash
cp env_sample.txt .env
```

> Docker Compose automatically overrides DB settings to use PostgreSQL.  
> You do not need to edit `.env` for basic Docker usage.

### Step 2 — Build and start all services

```bash
docker compose up --build
```

First run will:
1. Build Django image
2. Start **PostgreSQL** (port 5432)
3. Start **Redis** (port 6379)
4. Wait for database
5. Run migrations
6. Seed demo data
7. Start Django on port **8000**

### Step 3 — Open in browser

| Service | URL |
|---------|-----|
| API | http://localhost:8000/api/ |
| Swagger UI | http://localhost:8000/api/docs/ |
| ReDoc | http://localhost:8000/api/redoc/ |
| Django Admin | http://localhost:8000/admin/ |

### Run in background (detached)

```bash
docker compose up --build -d
```

### Stop services

```bash
docker compose down
```

### Stop and delete database (fresh start)

```bash
docker compose down -v
docker compose up --build
```

---

## Run Locally (without Docker)

> **Note:** Use `venv` in this folder. On Ubuntu, if `python` is missing, use `python3`.

```bash
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt  # or: requirements/development.txt
cp env_sample.txt .env
python manage.py migrate
python manage.py seed_demo_data
python manage.py runserver
```

Uses **SQLite** by default (from `.env`).

---

## Swagger API Docs

After server is running, open:

**Swagger UI:** http://localhost:8000/api/docs/

### How to test authenticated endpoints in Swagger

1. Open http://localhost:8000/api/docs/
2. Find **`POST /api/auth/login/`**
3. Click **Try it out**
4. Body:
   ```json
   {
     "email": "rahim@example.com",
     "password": "demo1234"
   }
   ```
5. Copy the `access` token from response
6. Click **Authorize** button (top right, lock icon)
7. Enter: `Bearer <your-access-token>`
8. Now all `/api/me/` endpoints will work

**ReDoc (alternative docs):** http://localhost:8000/api/redoc/  
**OpenAPI JSON schema:** http://localhost:8000/api/schema/

---

## Demo Accounts

| Role | Email | Password |
|------|-------|----------|
| Customer | rahim@example.com | demo1234 |
| Agent | sara@company.com | demo1234 |
| Admin | admin@company.com | demo1234 |

---

## API Endpoints

### globalapi (public — no token)

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/auth/register/` | Register customer |
| POST | `/api/auth/login/` | Login, get JWT tokens |
| POST | `/api/auth/google/` | Sign in with Google ID token |
| POST | `/api/auth/password-reset/` | Request password reset email |
| POST | `/api/auth/password-reset/confirm/` | Confirm reset with uid + token |
| POST | `/api/auth/refresh/` | Refresh access token |

### meapi (JWT required)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/me/auth/me/` | Current user profile |
| GET/POST | `/api/me/tickets/` | List / create tickets |
| GET | `/api/me/tickets/{ticket_uid}/` | Ticket detail |
| POST | `/api/me/tickets/{ticket_uid}/comments/` | Add reply |
| POST | `/api/me/tickets/{ticket_uid}/assign/` | Assign agent |
| POST | `/api/me/tickets/{ticket_uid}/resolve/` | Resolve ticket |
| GET | `/api/me/tickets/{ticket_uid}/activities/` | Activity timeline |
| GET/POST | `/api/me/chat/sessions/` | Chat sessions |
| POST | `/api/me/chat/sessions/{id}/messages/` | Send message (AI reply or agent chat) |
| POST | `/api/me/chat/sessions/{id}/escalate/` | Escalate to human agent (customer) |
| POST | `/api/me/chat/ask/` | RAG Q&A (one-shot) |
| GET/POST | `/api/me/knowledge/documents/` | List / upload documents (admin) |
| DELETE | `/api/me/knowledge/documents/{id}/` | Delete document (admin) |
| GET/POST | `/api/me/sla/` | List / create SLA policies (POST: admin) |
| GET | `/api/me/analytics/dashboard/` | Analytics (admin) |
| GET | `/api/me/agents/workload/` | Agent workload |

---

## Useful Docker Commands

```bash
# View running containers
docker compose ps

# View logs (live)
docker compose logs -f web

# Run Django shell inside container
docker compose exec web python manage.py shell

# Run migrations manually
docker compose exec web python manage.py migrate

# Re-seed demo data
docker compose exec web python manage.py seed_demo_data

# Create superuser
docker compose exec web python manage.py createsuperuser

# Rebuild after code changes
docker compose up --build

# Stop everything
docker compose down
```

---

## Docker Services

| Container | Image | Port | Purpose |
|-----------|-------|------|---------|
| `supportai_web` | Custom (Django) | 8000 | REST API + Swagger |
| `supportai_db` | postgres:16-alpine | 5432 | PostgreSQL database |
| `supportai_redis` | redis:7-alpine | 6379 | Redis (Celery/Channels later) |

---

## Troubleshooting

### Port 8000 already in use

```bash
# Find and stop process using port 8000
sudo lsof -i :8000
# Or change port in docker-compose.yml: "8001:8000"
```

### Database connection error

```bash
docker compose down -v
docker compose up --build
```

### Permission denied on entrypoint.sh

```bash
chmod +x entrypoint.sh
docker compose up --build
```

### Swagger Authorize not working

Make sure format is: `Bearer eyJhbGciOi...` (include the word `Bearer` + space)

### Frontend cannot connect to API

Add frontend URL to `CORS_ALLOWED_ORIGINS` in `.env`:

```
CORS_ALLOWED_ORIGINS=http://localhost:5173,http://127.0.0.1:5173
```

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `SECRET_KEY` | — | Django secret key |
| `DEBUG` | True | Debug mode |
| `DB_ENGINE` | sqlite3 | Database engine |
| `DB_HOST` | db (docker) | Database host |
| `SEED_DEMO_DATA` | false | Auto-seed on startup |
| `CORS_ALLOWED_ORIGINS` | localhost:5173 | Frontend URLs |
| `JWT_ACCESS_MINUTES` | 60 | Access token lifetime |

See `env_sample.txt` for full list.
