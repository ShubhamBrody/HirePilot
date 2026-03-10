# HirePilot — System Architecture Document

## 1. System Overview

HirePilot is a production-grade AI-powered job search automation platform that helps users
automatically discover jobs, tailor resumes, contact recruiters, and track applications.

---

## 2. High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          CLIENT LAYER                                   │
│  ┌─────────────┐  ┌──────────────┐  ┌──────────────┐  ┌────────────┐  │
│  │  Dashboard   │  │ LaTeX Editor │  │  App Tracker │  │  Settings  │  │
│  │  (Next.js)   │  │ (Monaco)     │  │  (React)     │  │  (React)   │  │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘  └─────┬──────┘  │
│         └──────────────────┴─────────────────┴────────────────┘         │
│                              │ HTTPS/WSS                                │
└──────────────────────────────┼──────────────────────────────────────────┘
                               │
┌──────────────────────────────┼──────────────────────────────────────────┐
│                         API GATEWAY (Nginx)                             │
│                     Rate Limiting · CORS · TLS                          │
└──────────────────────────────┼──────────────────────────────────────────┘
                               │
┌──────────────────────────────┼──────────────────────────────────────────┐
│                     BACKEND SERVICES (FastAPI)                          │
│                                                                         │
│  ┌───────────┐  ┌────────────┐  ┌────────────┐  ┌───────────────────┐  │
│  │  Auth      │  │  Jobs API  │  │ Resume API │  │ Applications API  │  │
│  │  Service   │  │  Service   │  │  Service   │  │   Service         │  │
│  └─────┬─────┘  └─────┬──────┘  └─────┬──────┘  └────────┬──────────┘  │
│        │               │               │                  │             │
│  ┌─────┴───────────────┴───────────────┴──────────────────┴──────────┐  │
│  │                    SERVICE LAYER (Business Logic)                  │  │
│  │  ┌──────────┐ ┌──────────┐ ┌───────────┐ ┌──────────┐ ┌────────┐ │  │
│  │  │ Job      │ │ Recruiter│ │ Resume    │ │ Applica- │ │ Messag-│ │  │
│  │  │ Discovery│ │ Finder   │ │ Tailoring │ │ tion Bot │ │ ing    │ │  │
│  │  └────┬─────┘ └────┬─────┘ └─────┬─────┘ └────┬─────┘ └───┬────┘ │  │
│  └───────┼────────────┼─────────────┼────────────┼────────────┼──────┘  │
│          │            │             │            │            │          │
│  ┌───────┴────────────┴─────────────┴────────────┴────────────┴──────┐  │
│  │                  REPOSITORY LAYER (Data Access)                    │  │
│  └───────────────────────────────┬───────────────────────────────────┘  │
│                                  │                                      │
└──────────────────────────────────┼──────────────────────────────────────┘
                                   │
        ┌──────────────────────────┼──────────────────────────┐
        │                          │                          │
┌───────┴──────┐  ┌────────────────┴──────────┐  ┌───────────┴──────────┐
│  PostgreSQL  │  │  Redis + Celery Workers   │  │  S3/MinIO Storage    │
│  (Primary DB)│  │  (Task Queue + Cache)     │  │  (PDFs, Resumes)     │
└──────────────┘  └───────────────────────────┘  └──────────────────────┘
                                   │
                  ┌────────────────┴──────────────────┐
                  │      EXTERNAL SERVICES             │
                  │  ┌──────────┐  ┌───────────────┐  │
                  │  │ OpenAI   │  │ Job Boards    │  │
                  │  │ API      │  │ (LinkedIn,    │  │
                  │  │          │  │  Indeed, etc) │  │
                  │  └──────────┘  └───────────────┘  │
                  └────────────────────────────────────┘
```

---

## 3. Module Breakdown

### 3.1 Job Scraper Service
- **Purpose**: Discover and collect job listings from multiple sources
- **Sources**: LinkedIn, Indeed, Naukri, company career pages
- **Tech**: Playwright for dynamic pages, httpx for API-based scraping
- **Output**: Normalized `JobListing` objects stored in PostgreSQL
- **Scheduling**: Celery Beat periodic tasks

### 3.2 Recruiter Finder Service
- **Purpose**: Identify recruiters/hiring managers for discovered jobs
- **Approach**: LinkedIn profile search, company page analysis
- **Output**: `Recruiter` records linked to `JobListing`

### 3.3 Messaging Agent
- **Purpose**: Send connection requests and personalized messages
- **AI**: GPT-4 generates context-aware messages
- **Safety**: Rate limiting, human-like delays, daily caps

### 3.4 Resume Tailoring AI
- **Purpose**: Adapt base resume to match job descriptions
- **Process**: Extract JD keywords → Match against resume → Generate tailored version
- **Output**: New `ResumeVersion` with LaTeX source + compiled PDF

### 3.5 LaTeX Resume Editor
- **Purpose**: Browser-based resume editor (Overleaf-like)
- **Tech**: Monaco Editor + server-side LaTeX compilation
- **Features**: Syntax highlighting, real-time preview, templates, version history

### 3.6 Application Automation Bot
- **Purpose**: Auto-fill and submit job applications
- **Tech**: Playwright with human-like interaction patterns
- **Safety**: CAPTCHA detection, rate limits, audit logging

### 3.7 Application Tracker
- **Purpose**: Track all applications with status pipeline
- **Statuses**: Applied → Interview → Offer/Rejected/Withdrawn
- **Features**: Filtering, analytics, timeline view

### 3.8 Resume Version Manager
- **Purpose**: Manage resume versions with full history
- **Features**: Diff view, tagging, per-application linking

---

## 4. Database Design (see schema files for full DDL)

### Entity Relationship Overview
```
User ──┬── ResumeVersion ──── Application
       │         │
       ├── JobListing ────── Recruiter
       │         │
       ├── OutreachMessage
       │
       └── AuditLog
```

---

## 5. API Design

| Method | Endpoint                          | Description                    |
|--------|-----------------------------------|--------------------------------|
| POST   | /api/v1/auth/register             | User registration              |
| POST   | /api/v1/auth/login                | Login + JWT                    |
| GET    | /api/v1/jobs                      | List discovered jobs           |
| POST   | /api/v1/jobs/search               | Trigger job search             |
| GET    | /api/v1/jobs/{id}/match-score     | AI match score for a job       |
| GET    | /api/v1/recruiters                | List recruiters                |
| POST   | /api/v1/recruiters/{id}/outreach  | Send outreach message          |
| GET    | /api/v1/resumes                   | List resume versions           |
| POST   | /api/v1/resumes                   | Create resume version          |
| POST   | /api/v1/resumes/tailor            | AI-tailor resume for job       |
| POST   | /api/v1/resumes/{id}/compile      | Compile LaTeX to PDF           |
| GET    | /api/v1/resumes/{id}/pdf          | Download PDF                   |
| GET    | /api/v1/applications              | List applications              |
| POST   | /api/v1/applications              | Create application             |
| PATCH  | /api/v1/applications/{id}/status  | Update application status      |
| POST   | /api/v1/applications/{id}/apply   | Auto-apply to job              |
| GET    | /api/v1/templates                 | List LaTeX templates           |
| GET    | /api/v1/analytics/dashboard       | Dashboard analytics            |

---

## 6. Security Architecture

1. **Authentication**: JWT with refresh tokens, bcrypt password hashing
2. **Credential Storage**: AES-256 encrypted at rest for platform credentials
3. **Rate Limiting**: Per-user + global rate limits on all automation
4. **CAPTCHA Detection**: Playwright monitors for CAPTCHA challenges, pauses and alerts
5. **Audit Logging**: Every automation action logged with timestamp, IP, result
6. **Input Validation**: Pydantic models validate all API inputs
7. **CORS**: Strict origin whitelist
8. **Secrets Management**: Environment variables via `.env`, never committed

---

## 7. Deployment Strategy

### Development
- Docker Compose with all services
- Hot reload for frontend and backend

### Staging
- Kubernetes cluster with separate namespaces
- CI/CD via GitHub Actions

### Production
- AWS ECS/EKS or self-hosted Kubernetes
- RDS for PostgreSQL
- ElastiCache for Redis
- S3 for file storage
- CloudFront CDN for frontend
- ALB with WAF for API gateway

---

## 8. MVP Roadmap

### Phase 1 (Weeks 1-2): Foundation
- [x] Project structure
- [x] Database schema
- [x] Auth system
- [x] Basic API endpoints
- [x] Frontend scaffolding

### Phase 2 (Weeks 3-4): Core Features
- [ ] Job scraper (LinkedIn, Indeed)
- [ ] Resume upload & version management
- [ ] LaTeX editor integration
- [ ] Application tracker UI

### Phase 3 (Weeks 5-6): AI Features
- [ ] Resume tailoring AI
- [ ] Job match scoring
- [ ] Recruiter discovery
- [ ] Message generation

### Phase 4 (Weeks 7-8): Automation
- [ ] Application auto-fill bot
- [ ] Recruiter outreach automation
- [ ] Scheduling & queue management

### Phase 5 (Weeks 9-10): Polish & Scale
- [ ] Analytics dashboard
- [ ] Performance optimization
- [ ] Security audit
- [ ] Load testing
- [ ] Documentation

---

## 9. Scaling Plan

### Horizontal Scaling
- Stateless API servers behind load balancer
- Celery workers scale independently per queue
- Read replicas for PostgreSQL

### Caching Strategy
- Redis caching for job listings (TTL: 1 hour)
- Resume compilation results cached
- Session data in Redis

### Queue Scaling
- Separate Celery queues: `scraping`, `ai`, `automation`, `messaging`
- Priority-based routing
- Dead letter queues for failed tasks

### Storage Scaling
- S3 with lifecycle policies
- CDN for compiled PDFs
- Database partitioning by date for audit logs
