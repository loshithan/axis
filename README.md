# AXIS — AI Workforce Scheduling Platform

AXIS is an AI-powered workforce scheduling system built for Hemas Holdings. It manages shift creation, leave requests, swap management, and overtime (OT) coverage across multiple Strategic Business Units (SBUs) and departments.

---

## Architecture

```
axis/
├── backend/              # FastAPI backend (Python)
│   ├── app/
│   │   ├── main.py       # API routes
│   │   ├── models/       # SQLAlchemy ORM models
│   │   ├── schemas/      # Pydantic request/response schemas
│   │   ├── services/     # Business logic (axis_service.py)
│   │   └── rules/        # Scheduling validation rules engine
│   ├── agents/           # AI orchestrator (DeepSeek LLM)
│   ├── seed.py           # Database seeder
│   └── requirements.txt
├── shift-genie-main/     # React + Vite frontend
│   └── src/
│       └── components/   # ChatPanel, ShiftCalendar, OTPanel, SwapPanel, ShiftModal
├── configs/              # SBU configuration profiles
│   ├── hospitals.json    # Hemas Hospitals SBU config
│   └── mobility.json     # Mobility SBU config
├── db/
│   └── init.sql          # Database schema
└── docker-compose.yml
```

---

## Prerequisites

- [Docker Desktop](https://www.docker.com/products/docker-desktop/)
- Node.js 18+ (for local frontend development)
- Python 3.11+ (for local backend development)

---

## Quick Start (Docker)

### 1. Get a DeepSeek API Key

The AI chat features require a DeepSeek API key.

1. Sign up at [platform.deepseek.com](https://platform.deepseek.com)
2. Go to **API Keys** and create a new key
3. Copy the key — you will need it in the next step

### 2. Run the Application

```bash
# Clone the repository
git clone <repo-url>
cd axis

# Create your environment file and add your DeepSeek API key
cp .env.example .env
# Open .env and set:
#   DEEPSEEK_API_KEY=sk-your-key-here

# Start all services
docker compose up --build

# Seed the database (first time only)
docker exec axis-backend python seed.py
```

> **Note:** Without `DEEPSEEK_API_KEY` the application will still run but AI chat scheduling will fall back to a basic heuristic mode with limited natural language understanding.

Services will be available at:
| Service  | URL                   |
|----------|-----------------------|
| Frontend | http://localhost:8080 |
| Backend  | http://localhost:8001 |
| Database | localhost:5432        |

---

## Local Development (without Docker)

### Backend

```bash
cd backend
pip install -r requirements.txt

# Set environment variables
export DATABASE_URL="postgresql+asyncpg://axis_user:axis_dev_password@localhost:5432/axis"
export DEEPSEEK_API_KEY="your-key-here"

# Run with auto-reload
uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload

# Seed the database
python seed.py
```

### Frontend

```bash
cd shift-genie-main
npm install
npm run dev
```

---

## Environment Variables

| Variable           | Required | Description                              |
|--------------------|----------|------------------------------------------|
| `DATABASE_URL`     | Yes      | PostgreSQL connection string             |
| `DEEPSEEK_API_KEY` | No       | DeepSeek API key for AI chat features    |
| `DEEPSEEK_BASE_URL`| No       | DeepSeek base URL (default: api.deepseek.com) |
| `DEEPSEEK_MODEL`   | No       | Model name (default: deepseek-chat)      |
| `SENDGRID_API_KEY` | No       | SendGrid key for email notifications     |
| `SMTP_HOST`        | No       | SMTP host (alternative to SendGrid)      |
| `SMTP_PORT`        | No       | SMTP port (default: 587)                 |
| `SMTP_USER`        | No       | SMTP username                            |
| `SMTP_PASSWORD`    | No       | SMTP password                            |
| `SMTP_FROM`        | No       | Sender email address                     |

---

## Key Features

- **AI Chat Scheduling** — Natural language shift creation (e.g. "Create ICU shifts for nurses from today to April 15, morning and evening only")
- **Multi-role Support** — Separate nurse and doctor shifts with role enforcement across scheduling, swaps, and OT
- **Leave & Swap Management** — Automated swap candidate finding with validation (certifications, weekly hours, rest periods, role match)
- **OT Management** — Notify eligible staff for open shifts; manager assigns from applicants
- **Shift Calendar** — Visual calendar with per-role colour coding

---

## Resetting Data (keep seed)

```bash
# Via Docker
docker exec axis-backend python -c "
import asyncio, asyncpg, os
async def run():
    conn = await asyncpg.connect(os.environ['DATABASE_URL'].replace('+asyncpg',''))
    await conn.execute('TRUNCATE shifts, leave_requests, escalations, ot_requests, ot_applications, agent_logs, availability RESTART IDENTITY CASCADE;')
    await conn.close()
asyncio.run(run())
"

# Via psql directly
psql -U axis_user -d axis -c "TRUNCATE shifts, leave_requests, escalations, ot_requests, ot_applications, agent_logs, availability RESTART IDENTITY CASCADE;"
```
