# HirePilot — System Architecture Diagrams

## 1. High-Level System Architecture

```mermaid
graph TB
    subgraph Client["Frontend (Next.js)"]
        UI[React Pages]
        Monaco[Monaco LaTeX Editor]
        Store[Zustand Stores]
    end

    subgraph API["Backend (FastAPI)"]
        Router[API v1 Router]
        Auth[Auth Service]
        Services[Service Layer]
        Repos[Repository Layer]
    end

    subgraph Workers["Celery Workers"]
        ScrapeQ[Scraping Queue]
        AIQ[AI Queue]
        AutoQ[Automation Queue]
        OutQ[Outreach Queue]
    end

    subgraph AI["AI / Automation"]
        Scraper[Job Scraper<br/>LinkedIn · Indeed · Naukri]
        Finder[Recruiter Finder]
        Tailor[Resume Tailoring AI]
        MsgGen[Message Generator]
        AppBot[Application Bot]
        LaTeX[LaTeX Compiler]
    end

    subgraph Storage["Data Layer"]
        PG[(PostgreSQL)]
        Redis[(Redis)]
        S3[(MinIO / S3)]
    end

    subgraph External["External Services"]
        OpenAI[OpenAI GPT-4]
        LI[LinkedIn]
        Indeed[Indeed]
        Naukri[Naukri]
    end

    UI --> Router
    Store --> Router
    Router --> Auth
    Router --> Services
    Services --> Repos
    Repos --> PG
    Services --> Redis
    Services -.-> ScrapeQ
    Services -.-> AIQ
    Services -.-> AutoQ
    Services -.-> OutQ

    ScrapeQ --> Scraper
    AIQ --> Tailor
    AIQ --> LaTeX
    AutoQ --> AppBot
    OutQ --> MsgGen
    OutQ --> Finder

    Scraper --> LI
    Scraper --> Indeed
    Scraper --> Naukri
    Tailor --> OpenAI
    MsgGen --> OpenAI
    AppBot --> LI
    Finder --> LI

    LaTeX --> S3
    Tailor --> S3

    Redis --> ScrapeQ
    Redis --> AIQ
    Redis --> AutoQ
    Redis --> OutQ
```

## 2. Request Flow — Resume Tailoring Pipeline

```mermaid
sequenceDiagram
    participant U as User
    participant FE as Frontend
    participant API as FastAPI
    participant CQ as Celery Queue
    participant AI as ResumeTailoringService
    participant GPT as OpenAI GPT-4
    participant TEX as LaTeX Compiler
    participant S3 as MinIO/S3
    participant DB as PostgreSQL

    U->>FE: Click "Tailor for Job"
    FE->>API: POST /resumes/{id}/tailor
    API->>CQ: Dispatch tailor_resume task
    API-->>FE: 202 Accepted (task_id)

    CQ->>AI: Execute tailor_resume
    AI->>DB: Load resume LaTeX + job description
    AI->>GPT: Analyze JD → extract requirements
    GPT-->>AI: Structured requirements JSON
    AI->>GPT: Tailor resume LaTeX for JD
    GPT-->>AI: Tailored LaTeX + changes summary
    AI->>GPT: Compute match score
    GPT-->>AI: Score (0-100)

    AI->>TEX: Compile tailored LaTeX
    TEX-->>AI: PDF bytes
    AI->>S3: Upload PDF
    S3-->>AI: PDF URL

    AI->>DB: Save new ResumeVersion + update match score
    AI-->>CQ: Result {version_id, pdf_url, score}

    FE->>API: Poll status / WebSocket
    API-->>FE: Tailored resume ready
    FE-->>U: Show tailored resume + PDF preview
```

## 3. Entity Relationship Diagram

```mermaid
erDiagram
    USER ||--o{ JOB_LISTING : discovers
    USER ||--o{ RESUME_VERSION : owns
    USER ||--o{ APPLICATION : submits
    USER ||--o{ RECRUITER : tracks
    USER ||--o{ AUDIT_LOG : generates

    JOB_LISTING ||--o{ APPLICATION : "applied to"
    RESUME_VERSION ||--o{ APPLICATION : "used for"
    RECRUITER ||--o{ OUTREACH_MESSAGE : receives

    USER {
        uuid id PK
        string email UK
        string hashed_password
        string full_name
        json job_preferences
        text encrypted_platform_credentials
        datetime created_at
    }

    JOB_LISTING {
        uuid id PK
        uuid user_id FK
        string title
        string company
        string location
        text description
        string url
        enum source "linkedin|indeed|naukri|other"
        string external_id
        float match_score
        json skills
        datetime created_at
    }

    RESUME_VERSION {
        uuid id PK
        uuid user_id FK
        string name
        text latex_content
        bool is_master
        int version_number
        string pdf_url
        bool compiled_successfully
        json compilation_errors
        uuid tailored_for_job_id FK
        text ai_changes_summary
        datetime created_at
    }

    APPLICATION {
        uuid id PK
        uuid user_id FK
        uuid job_listing_id FK
        uuid resume_version_id FK
        enum status "saved|applied|screening|interviewing|offer|accepted|rejected|withdrawn|no_response"
        enum method "manual|auto_bot|easy_apply"
        text cover_letter
        text notes
        datetime applied_date
        datetime interview_date
        datetime offer_date
        datetime created_at
    }

    RECRUITER {
        uuid id PK
        uuid user_id FK
        string name
        string title
        string company
        string linkedin_url
        enum connection_status "not_connected|pending|connected|ignored"
        datetime last_contacted
        datetime created_at
    }

    OUTREACH_MESSAGE {
        uuid id PK
        uuid recruiter_id FK
        string message_type
        text content
        enum status "draft|sent|delivered|replied|failed"
        datetime sent_at
        text error_message
    }

    AUDIT_LOG {
        uuid id PK
        uuid user_id FK
        string action
        string resource_type
        uuid resource_id
        json details
        datetime created_at
    }
```

## 4. Deployment Architecture

```mermaid
graph LR
    subgraph Internet
        Browser[User Browser]
    end

    subgraph Docker["Docker Compose Stack"]
        subgraph Frontend
            Next[Next.js :3000]
        end

        subgraph Backend
            FastAPI[FastAPI :8000]
            CW1[Celery Worker<br/>scraping,ai]
            CW2[Celery Worker<br/>automation,outreach]
            CB[Celery Beat<br/>scheduler]
        end

        subgraph Data
            PG[(PostgreSQL :5432)]
            Redis[(Redis :6379)]
            MinIO[(MinIO :9000)]
        end
    end

    Browser --> Next
    Next --> FastAPI
    FastAPI --> PG
    FastAPI --> Redis
    FastAPI -.-> Redis
    Redis --> CW1
    Redis --> CW2
    Redis --> CB
    CW1 --> PG
    CW1 --> MinIO
    CW2 --> PG
```

## 5. Celery Task Flow

```mermaid
graph TD
    subgraph Beat["Celery Beat (Scheduler)"]
        S1[Every 6h: scrape_jobs_periodic]
        S2[Daily 3AM: cleanup_stale_applications]
        S3[9AM/2PM: send_scheduled_followups]
    end

    subgraph Queues
        QS[Scraping Queue]
        QA[AI Queue]
        QAuto[Automation Queue]
        QO[Outreach Queue]
    end

    subgraph Tasks
        T1[scrape_jobs]
        T2[tailor_resume]
        T3[batch_match_score]
        T4[compile_resume]
        T5[auto_apply_job]
        T6[bulk_auto_apply]
        T7[find_recruiters]
        T8[send_connection_request]
        T9[send_followup_message]
    end

    S1 --> QS
    S2 --> QAuto
    S3 --> QO

    QS --> T1
    QA --> T2
    QA --> T3
    QA --> T4
    QAuto --> T5
    QAuto --> T6
    QO --> T7
    QO --> T8
    QO --> T9

    T6 -.->|dispatches per job| T5
```
