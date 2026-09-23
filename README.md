# Rivu AI

### The Data Refinery for messy business data.

Rivu takes raw operational data and turns it into **clean, validated, explainable and analysis-ready data** — with an AI-assisted refinement layer that keeps humans in control.

> **Upload → Understand → Detect → Recommend → Approve → Refine → Measure → Export**

---

## ✦ What Rivu does

Business data rarely arrives ready for analysis. Rivu creates a structured refinery pipeline around it.

| Stage | What happens |
|---|---|
| **Ingest** | CSV, XLSX and supported data sources enter a tenant-isolated workspace |
| **Profile** | Rows, columns, types, nulls, duplicates and distributions are measured |
| **Quality** | Data health is scored across completeness, validity, consistency, uniqueness and integrity |
| **AI Refinery** | AI proposes a structured transformation plan from measured dataset facts |
| **Review** | Users inspect operations and preview changes before approval |
| **Deterministic Transform** | Approved operations run through the cleaning engine |
| **Re-profile** | The refined version is measured again |
| **Intelligence** | Rivu turns measured results into an executive data report |
| **Export** | Refined data and reports are downloaded for downstream analytics |

### The core principle

**AI recommends. Deterministic code executes. Versions preserve history.**

Rivu does not silently mutate an uploaded dataset.

---

## ⚡ Product architecture

```text
                         ┌─────────────────────────┐
                         │        RIVU WEB         │
                         │ Next.js + TypeScript    │
                         │ Dashboard / Explorer    │
                         └────────────┬────────────┘
                                      │ HTTPS + JWT
                                      ▼
                         ┌─────────────────────────┐
                         │       FASTAPI API       │
                         │ Auth / Tenant / Dataset │
                         │ Quality / Refinement    │
                         └───────┬─────────┬───────┘
                                 │         │
                    ┌────────────┘         └──────────────┐
                    ▼                                     ▼
          ┌──────────────────┐                 ┌──────────────────┐
          │     REFINERY     │                 │   AI PROVIDER    │
          │ Polars / Python  │◄───────────────►│ Groq abstraction │
          │ Profile / Clean  │                 │ Plans, insights  │
          └────────┬─────────┘                 └──────────────────┘
                   │
          ┌────────┴─────────┐
          ▼                  ▼
 ┌─────────────────┐  ┌──────────────────┐
 │ PostgreSQL      │  │ Object Storage   │
 │ versions /      │  │ raw + refined    │
 │ profiles / jobs │  │ datasets/files   │
 └─────────────────┘  └──────────────────┘
```

---

## 🧠 AI Refinery

The AI layer is deliberately separated from the execution engine.

**Measured data facts → AI transformation plan → human approval → deterministic execution**

A plan can contain operations such as:

- null handling
- duplicate handling
- type normalization
- string normalization
- date normalization
- validation-oriented cleanup
- schema-aware transformations

Every approved refinement creates a **new dataset version** rather than rewriting the raw source.

---

## 📊 Intelligence workspace

Rivu's authenticated dataset workspace provides:

- Data Health score
- quality dimensions
- column-level health matrix
- null distribution
- data-type distribution
- issue severity mix
- refinement impact
- real-data explorer
- search + pagination + sorting
- before/after transformation preview
- AI refinement plan
- refined dataset downloads
- schema export
- quality PDF
- executive intelligence PDF

The dashboard is designed as an operational data workspace rather than a decorative AI demo.

---

## 🏗️ Repository structure

```text
rivu-ai/
│
├── app/                         # Next.js application
│   ├── dashboard/               # Authenticated product workspace
│   │   └── dataset/[id]/        # Dataset intelligence + refinery UI
│   ├── login/                   # Authentication
│   ├── signup/                  # Workspace onboarding
│   ├── page.tsx                 # Public landing page
│   └── globals.css              # Global visual system
│
├── lib/                         # Frontend product primitives
│   ├── api.ts                   # Authenticated API client
│   ├── BrandLogo.tsx            # Rivu identity
│   ├── CursorField.tsx          # Interactive visual layer
│   └── ProcessingRail.tsx       # Processing state UI
│
├── backend/
│   ├── app/
│   │   ├── api/v1/              # REST API endpoints
│   │   ├── ai/                  # AI provider + planning layer
│   │   ├── core/                # config, DB, security, storage
│   │   ├── ingestion/            # file parsing / ingestion
│   │   ├── models/              # SQLAlchemy domain models
│   │   ├── services/             # business logic
│   │   └── workers/              # processing jobs
│   ├── alembic/                 # database migrations
│   ├── tests/                   # backend tests
│   ├── Dockerfile
│   └── requirements.txt
│
├── db/                          # database reference material
├── e2e/                         # Playwright product-flow tests
├── .github/workflows/           # CI + security + E2E
├── docs/                        # architecture and engineering docs
└── package.json                 # frontend + E2E tooling
```

---

## 🔐 Data integrity & security

Rivu is built around controlled data movement:

- Raw version 1 remains immutable.
- Refinement requires an explicit approval step.
- Every refinement creates a new version.
- Tenant isolation is enforced through authenticated organization context.
- Secrets belong in deployment environment stores, never Git.
- JWT authentication protects API access.
- Passwords use PBKDF2-SHA256 hashing.
- Production configuration disables automatic schema creation.
- Database changes are handled through migrations.
- CI/security scanning is part of the release process.

---

## 🛠️ Stack

**Frontend**

Next.js · React · TypeScript · CSS Modules · Lucide

**Backend**

FastAPI · Python · SQLAlchemy async · Pydantic

**Data**

Polars · pandas/openpyxl · PostgreSQL · S3-compatible object storage

**AI**

Provider abstraction · Groq-compatible AI provider

**Quality**

Playwright · GitHub Actions · CodeQL · dependency/security checks

---

## 🚀 Local development

### Frontend

```bash
npm install
npm run dev
```

### Production build

```bash
npm run build
npm start
```

### E2E

```bash
npx playwright install
npm run test:e2e
```

### Backend

```bash
cd backend
pip install -r requirements.txt
```

Configure the environment from:

```text
backend/.env.example
```

Production secrets must be provided through the deployment environment.

---

## 🔄 Release philosophy

Rivu treats production readiness as a gate, not a screenshot.

A release should verify:

1. frontend build
2. backend tests
3. authentication
4. tenant isolation
5. ingestion formats
6. profiling
7. quality analysis
8. AI planning
9. deterministic transformation
10. version creation
11. artifact downloads
12. complete E2E flow
13. security checks
14. deployed performance/load behaviour

**A green UI is not proof of a green data pipeline.**

---

## 🧭 Roadmap

### Now
- Reliable refinery pipeline
- Dataset intelligence workspace
- Human-approved AI refinement
- Versioned outputs
- Executive reporting

### Next
- Durable queue-backed processing
- Larger dataset streaming paths
- More connectors
- Saved transformation recipes
- Team collaboration and audit trails
- Advanced lineage and observability

### Scale
Heavy profiling/refinement should move to durable queue-backed workers as traffic and dataset size increase. High request-rate targets must be validated with staged load tests rather than assumed from source code.

---

## Proprietary

**Rivu AI by WaterTing**

© 2026 WaterTing. All rights reserved.
