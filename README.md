# Rivu by WaterTing

**Turn messy data into production-ready intelligence.**

Rivu is an AI-native Data Refinery that takes raw, inconsistent, and unstructured datasets and transforms them into clean, validated, structured, and analytically ready data intelligence.

---

## The Pipeline

```
RAW DATA
  → UNDERSTANDING
  → QUALITY ANALYSIS
  → CLEANING
  → NORMALIZATION
  → VALIDATION
  → STRUCTURING
  → ANALYTICS
  → DATA INTELLIGENCE
```

---

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | Next.js 14, TypeScript, Tailwind CSS |
| Backend | Python, FastAPI, Polars |
| Database | Neon PostgreSQL |
| AI | Groq (Llama 3.3 70B) with provider abstraction |
| Storage | S3-compatible (MinIO for local dev) |
| Auth | JWT + bcrypt |

---

## Repository Structure

```
rivu/
  frontend/        Next.js application
  backend/         FastAPI backend
  db/              SQL schema + migrations
  docs/            Architecture & API docs
  scripts/         Dev & deployment scripts
  .env.example     Environment variable template
  docker-compose.yml  Local dev services
```

---

## Quick Start

### Prerequisites

- Python 3.11+
- Node.js 18+
- Docker (for local PostgreSQL + MinIO)

### Setup

```bash
# 1. Clone and enter the repo
cd rivu

# 2. Copy environment variables
cp .env.example .env
# Fill in your values in .env

# 3. Start local services
docker-compose up -d

# 4. Set up backend
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
cd ..

# 5. Set up database
psql $DATABASE_URL_SYNC < db/schema.sql

# 6. Start backend
cd backend
uvicorn app.main:app --reload --port 8000

# 7. Set up frontend (new terminal)
cd frontend
npm install
npm run dev
```

App will be running at:
- Frontend: http://localhost:3000
- Backend API: http://localhost:8000
- API Docs: http://localhost:8000/docs

---

## Core Principles

1. **LLM never directly modifies data** — AI only plans; deterministic code executes
2. **Original data is always preserved** — version 1 = raw, version 2+ = processed
3. **Every transformation is explainable** — before/after/reason/confidence
4. **Tenant isolation** — every resource is workspace-scoped
5. **Security first** — no arbitrary code execution, read-only SQL validation

---

## License

Proprietary — WaterTing © 2026
