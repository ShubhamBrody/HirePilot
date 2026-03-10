# HirePilot 🚀

**AI-Powered Job Search Automation Platform**

HirePilot automates your entire job search workflow — from discovering opportunities and tailoring resumes with AI, to auto-applying and tracking recruiter outreach.

---

## Features

| Module | Description |
|--------|-------------|
| **Job Scraper** | Multi-source scraping (LinkedIn, Indeed, Naukri) with deduplication |
| **Resume Tailoring AI** | GPT-4 powered resume optimization for each job description |
| **LaTeX Resume Editor** | Monaco-based editor with real-time compilation to PDF |
| **Application Bot** | Playwright automation for one-click job applications |
| **Recruiter Finder** | LinkedIn recruiter discovery at target companies |
| **Messaging Agent** | AI-generated connection requests, InMails, and follow-ups |
| **Application Tracker** | Full pipeline tracking (Saved → Applied → Interview → Offer) |
| **Analytics Dashboard** | Stats, match scores, and interview rate metrics |

## Tech Stack

| Layer | Technology |
|-------|-----------|
| **Frontend** | Next.js 14, React, TypeScript, Tailwind CSS, Monaco Editor |
| **Backend** | Python 3.11+, FastAPI, Pydantic v2, SQLAlchemy 2.0 (async) |
| **Database** | PostgreSQL 16 (asyncpg), Redis 7 |
| **Task Queue** | Celery + Redis (4 queues: scraping, ai, automation, outreach) |
| **AI** | OpenAI GPT-4 Turbo |
| **Automation** | Playwright (headless Chromium) |
| **Storage** | MinIO / S3-compatible (resume PDFs) |
| **Auth** | JWT (access + refresh tokens), bcrypt, AES-256 Fernet encryption |

## Project Structure

```
HirePilot/
├── backend/
│   ├── app/
│   │   ├── api/v1/endpoints/    # REST endpoints (auth, jobs, resumes, applications, recruiters)
│   │   ├── core/                # Config, database, security, logging
│   │   ├── models/              # SQLAlchemy ORM models (6 models)
│   │   ├── repositories/        # Data access layer (generic CRUD + domain repos)
│   │   ├── schemas/             # Pydantic request/response schemas
│   │   ├── services/            # Business logic + AI/automation services
│   │   └── tasks/               # Celery tasks (scraping, AI, automation, outreach)
│   ├── alembic/                 # Database migrations
│   ├── Dockerfile
│   └── pyproject.toml
├── frontend/
│   ├── src/
│   │   ├── app/                 # Next.js pages (dashboard, jobs, resumes, applications, recruiters, settings, login)
│   │   ├── components/          # Reusable UI components
│   │   ├── lib/                 # API client, utilities
│   │   └── stores/              # Zustand state management
│   ├── Dockerfile
│   └── package.json
├── docs/
│   └── DIAGRAMS.md              # Mermaid architecture diagrams
├── docker-compose.yml           # Full stack: PG, Redis, MinIO, backend, workers, frontend
├── ARCHITECTURE.md              # Detailed system design document
└── .gitignore
```

## Quick Start

### Prerequisites
- Docker & Docker Compose
- OpenAI API key

### 1. Clone & Configure

```bash
git clone https://github.com/ShubhamBrody/HirePilot.git
cd HirePilot

# Configure backend
cp backend/.env.example backend/.env
# Edit backend/.env → fill in OPENAI_API_KEY, SECRET_KEY, etc.
```

### 2. Launch with Docker Compose

```bash
docker compose up --build
```

This starts:
- **PostgreSQL** on `:5432`
- **Redis** on `:6379`
- **MinIO** on `:9000` (console: `:9001`)
- **FastAPI** on `:8000` (Swagger: `http://localhost:8000/docs`)
- **Celery Worker** (4 queues)
- **Celery Beat** (scheduled tasks)
- **Next.js Frontend** on `:3000`

### 3. Run Migrations

```bash
docker compose exec backend alembic upgrade head
```

### 4. Access

- **Frontend**: http://localhost:3000
- **API Docs**: http://localhost:8000/docs
- **MinIO Console**: http://localhost:9001 (minioadmin / minioadmin123)

## Local Development (without Docker)

### Backend

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate        # Windows
pip install -e ".[dev]"
playwright install chromium

# Start API
uvicorn app.main:app --reload --port 8000

# Start Celery worker (separate terminal)
celery -A app.tasks worker --loglevel=info -Q scraping,ai,automation,outreach

# Start Celery beat (separate terminal)
celery -A app.tasks beat --loglevel=info
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

## API Overview

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/auth/register` | Create account |
| POST | `/api/v1/auth/login` | Get JWT tokens |
| GET | `/api/v1/jobs` | List discovered jobs |
| POST | `/api/v1/jobs/scrape` | Trigger job scraping |
| GET | `/api/v1/resumes` | List resume versions |
| POST | `/api/v1/resumes/{id}/tailor` | AI-tailor resume for a job |
| POST | `/api/v1/resumes/{id}/compile` | Compile LaTeX to PDF |
| GET | `/api/v1/applications` | List applications |
| PATCH | `/api/v1/applications/{id}/status` | Update application status |
| POST | `/api/v1/applications/auto-apply` | Auto-apply to a job |
| GET | `/api/v1/recruiters` | List tracked recruiters |
| POST | `/api/v1/recruiters/find` | Find recruiters at company |
| POST | `/api/v1/recruiters/{id}/outreach` | Send outreach message |

## Architecture

See [ARCHITECTURE.md](ARCHITECTURE.md) for the full system design and [docs/DIAGRAMS.md](docs/DIAGRAMS.md) for Mermaid architecture diagrams.

## License

MIT
