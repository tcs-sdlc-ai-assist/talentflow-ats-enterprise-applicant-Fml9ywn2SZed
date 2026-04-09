# TalentFlow ATS

**Applicant Tracking System** — A modern, full-featured recruitment management platform built with Python and FastAPI.

## Overview

TalentFlow ATS streamlines the hiring process by providing a centralized platform for managing job postings, tracking applicants, scheduling interviews, and collaborating across hiring teams. Designed for small-to-mid-size companies and recruiting agencies seeking an efficient, self-hosted ATS solution.

## Features

- **Job Management** — Create, publish, and manage job postings with rich descriptions, requirements, and metadata
- **Candidate Tracking** — Track applicants through customizable hiring pipelines with stage-based workflows
- **Resume Parsing & Storage** — Upload and store candidate resumes with file management
- **Interview Scheduling** — Schedule and manage interviews with calendar integration support
- **Evaluation & Scoring** — Structured interview feedback and candidate scoring system
- **Team Collaboration** — Role-based access for recruiters, hiring managers, and admins
- **Dashboard & Analytics** — Real-time hiring metrics, pipeline analytics, and reporting
- **Email Notifications** — Automated notifications for status changes, interview reminders, and team updates
- **Search & Filtering** — Advanced search across candidates, jobs, and applications with multiple filter criteria
- **Audit Trail** — Complete activity logging for compliance and accountability

## Tech Stack

| Layer | Technology |
|---|---|
| **Backend Framework** | FastAPI (Python 3.11+) |
| **Database** | PostgreSQL (production) / SQLite (development) |
| **ORM** | SQLAlchemy 2.0 (async) |
| **Migrations** | Alembic |
| **Authentication** | JWT (python-jose) + bcrypt password hashing |
| **Validation** | Pydantic v2 |
| **Configuration** | pydantic-settings (.env) |
| **Task Queue** | FastAPI BackgroundTasks |
| **File Storage** | Local filesystem (configurable) |
| **Server** | Uvicorn (ASGI) |

## Folder Structure

```
talentflow-ats/
├── alembic/                    # Database migration scripts
│   ├── versions/               # Individual migration files
│   └── env.py                  # Alembic environment config
├── alembic.ini                 # Alembic configuration
├── app/
│   ├── __init__.py
│   ├── main.py                 # FastAPI application entry point
│   ├── config.py               # Application settings (BaseSettings)
│   ├── database.py             # Async SQLAlchemy engine & session
│   ├── dependencies.py         # Shared dependencies (auth, db session, pagination)
│   ├── models/                 # SQLAlchemy ORM models
│   │   ├── __init__.py
│   │   ├── user.py             # User & role models
│   │   ├── job.py              # Job posting model
│   │   ├── candidate.py        # Candidate profile model
│   │   ├── application.py      # Job application model
│   │   ├── interview.py        # Interview scheduling model
│   │   ├── evaluation.py       # Interview evaluation/feedback model
│   │   ├── department.py       # Department/team model
│   │   └── activity_log.py     # Audit trail model
│   ├── schemas/                # Pydantic request/response schemas
│   │   ├── __init__.py
│   │   ├── user.py
│   │   ├── job.py
│   │   ├── candidate.py
│   │   ├── application.py
│   │   ├── interview.py
│   │   ├── evaluation.py
│   │   └── common.py           # Shared schemas (pagination, health, etc.)
│   ├── routes/                 # API route handlers
│   │   ├── __init__.py
│   │   ├── auth.py             # Authentication endpoints
│   │   ├── users.py            # User management endpoints
│   │   ├── jobs.py             # Job posting endpoints
│   │   ├── candidates.py       # Candidate endpoints
│   │   ├── applications.py     # Application endpoints
│   │   ├── interviews.py       # Interview endpoints
│   │   ├── evaluations.py      # Evaluation endpoints
│   │   ├── departments.py      # Department endpoints
│   │   └── dashboard.py        # Analytics/dashboard endpoints
│   └── services/               # Business logic layer
│       ├── __init__.py
│       ├── auth.py             # Authentication & JWT logic
│       ├── user.py             # User CRUD operations
│       ├── job.py              # Job management logic
│       ├── candidate.py        # Candidate management logic
│       ├── application.py      # Application workflow logic
│       ├── interview.py        # Interview scheduling logic
│       ├── evaluation.py       # Evaluation logic
│       └── email.py            # Email notification service
├── tests/                      # Test suite
│   ├── __init__.py
│   ├── conftest.py             # Shared fixtures
│   ├── test_auth.py
│   ├── test_jobs.py
│   ├── test_candidates.py
│   └── test_applications.py
├── uploads/                    # Resume & file uploads directory
├── .env                        # Environment variables (not committed)
├── .env.example                # Example environment variables
├── requirements.txt            # Python dependencies
└── README.md                   # This file
```

## Setup Instructions

### Prerequisites

- Python 3.11 or higher
- PostgreSQL 14+ (production) or SQLite (development)
- pip (Python package manager)

### 1. Clone the Repository

```bash
git clone <repository-url>
cd talentflow-ats
```

### 2. Create a Virtual Environment

```bash
python -m venv venv
source venv/bin/activate        # macOS/Linux
# venv\Scripts\activate         # Windows
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure Environment Variables

Copy the example environment file and update values:

```bash
cp .env.example .env
```

Edit `.env` with your configuration:

```env
# Application
APP_NAME=TalentFlow ATS
DEBUG=true
SECRET_KEY=your-secret-key-change-in-production
ALLOWED_ORIGINS=http://localhost:3000,http://localhost:8000

# Database
DATABASE_URL=sqlite+aiosqlite:///./talentflow.db
# For PostgreSQL:
# DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/talentflow

# JWT
JWT_SECRET_KEY=your-jwt-secret-key-change-in-production
JWT_ALGORITHM=HS256
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=30
JWT_REFRESH_TOKEN_EXPIRE_DAYS=7

# Email (optional)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=your-app-password
EMAIL_FROM=noreply@talentflow.com

# File Uploads
UPLOAD_DIR=./uploads
MAX_UPLOAD_SIZE_MB=10
```

### 5. Run Database Migrations

```bash
alembic upgrade head
```

To create a new migration after model changes:

```bash
alembic revision --autogenerate -m "description of changes"
alembic upgrade head
```

### 6. Seed Initial Data (Optional)

```bash
python -m app.seeds
```

### 7. Start the Development Server

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

The API will be available at:
- **API Base URL:** `http://localhost:8000`
- **Interactive Docs (Swagger):** `http://localhost:8000/docs`
- **ReDoc:** `http://localhost:8000/redoc`
- **Health Check:** `http://localhost:8000/health`

## API Documentation

Once the server is running, visit `/docs` for the full interactive Swagger UI documentation. All endpoints require JWT authentication unless otherwise noted.

### Authentication Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/auth/register` | Register a new user |
| POST | `/api/v1/auth/login` | Login and receive JWT tokens |
| POST | `/api/v1/auth/refresh` | Refresh access token |
| POST | `/api/v1/auth/logout` | Logout (invalidate token) |
| GET | `/api/v1/auth/me` | Get current user profile |

### Core Resource Endpoints

| Resource | Base Path | Operations |
|----------|-----------|------------|
| Users | `/api/v1/users` | CRUD, role management |
| Jobs | `/api/v1/jobs` | CRUD, publish/archive |
| Candidates | `/api/v1/candidates` | CRUD, resume upload |
| Applications | `/api/v1/applications` | CRUD, stage transitions |
| Interviews | `/api/v1/interviews` | CRUD, scheduling |
| Evaluations | `/api/v1/evaluations` | CRUD, scoring |
| Departments | `/api/v1/departments` | CRUD |
| Dashboard | `/api/v1/dashboard` | Analytics, metrics |

## Roles & Permissions

| Role | Description | Permissions |
|------|-------------|-------------|
| **super_admin** | System administrator | Full access to all resources, user management, system configuration |
| **admin** | Organization admin | Manage users, departments, jobs, and all hiring activities |
| **hiring_manager** | Department hiring lead | Create/manage jobs for their department, review applications, schedule interviews, submit evaluations |
| **recruiter** | Recruitment specialist | Manage candidates, process applications, coordinate interviews, manage pipeline |
| **interviewer** | Interview participant | View assigned interviews, submit evaluations and feedback |
| **viewer** | Read-only access | View jobs, candidates, and application statuses (no modifications) |

## Testing

Run the test suite:

```bash
# Run all tests
pytest

# Run with verbose output
pytest -v

# Run specific test file
pytest tests/test_auth.py

# Run with coverage report
pytest --cov=app --cov-report=html
```

## Deployment

### Vercel Deployment

1. Install the Vercel CLI:

```bash
npm install -g vercel
```

2. Create a `vercel.json` in the project root:

```json
{
  "builds": [
    {
      "src": "app/main.py",
      "use": "@vercel/python"
    }
  ],
  "routes": [
    {
      "src": "/(.*)",
      "dest": "app/main.py"
    }
  ]
}
```

3. Set environment variables in the Vercel dashboard (Settings → Environment Variables). Use a PostgreSQL connection string for `DATABASE_URL` (e.g., from Neon, Supabase, or Railway).

4. Deploy:

```bash
vercel --prod
```

### Docker Deployment

```bash
docker build -t talentflow-ats .
docker run -p 8000:8000 --env-file .env talentflow-ats
```

### Production Recommendations

- Use PostgreSQL with `asyncpg` driver for production workloads
- Set `DEBUG=false` in production environment variables
- Use a strong, unique `SECRET_KEY` and `JWT_SECRET_KEY`
- Configure CORS `ALLOWED_ORIGINS` to your frontend domain only
- Set up a reverse proxy (nginx/Caddy) with HTTPS termination
- Enable structured logging and ship logs to a monitoring service
- Run with multiple Uvicorn workers: `uvicorn app.main:app --workers 4`

## Contributing

This is a private project. Please contact the project maintainers for contribution guidelines.

## License

**Private** — All rights reserved. This software is proprietary and confidential. Unauthorized copying, distribution, or modification is strictly prohibited.