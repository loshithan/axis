# AXIS: AI-Powered Workforce Scheduling System

Axis is an autonomous, agentic application designed to manage workforce scheduling, shift swapping, and compliance oversight. It leverages LLMs to interpret natural language commands from managers and execute complex backend rules automatically.

## System Architecture

- **Backend**: FastAPI (Python) driving the API REST endpoints.
- **Frontend**: Next.js (React) providing a modern manager dashboard.
- **Database**: PostgreSQL (with pgvector) for storing shifts, worker profiles, and rules.
- **AI Engine**: Python-based LangChain AI agents.
  - **Orchestrator Agent**: Triages natural language inputs and routes them.
  - **Scheduler Agent**: Uses a ReAct reasoning loop to assign multiple open shifts while optimizing for fairness constraints.
  - **Swap Agent**: Automatically finds valid coverage when a worker submits a leave request.
  - **Compliance Agent**: Scheduled background worker that audits the schedule for burnout risks and minimum rest violations.

## Prerequisites

- [Docker](https://www.docker.com/products/docker-desktop) and Docker Compose
- An API key from either DeepSeek or Groq (for the AI agents to function)

## Setup & Environment Variables

Before running the project, create a `.env` file in the root `axis` directory. 

```env
# Database
DATABASE_URL=postgresql+asyncpg://axis_user:axis_dev_password@localhost:5433/axis

# AI / LLM Keys (You must provide at least one of these)
DEEPSEEK_API_KEY=your_deepseek_key_here
GROQ_API_KEY=your_groq_key_here

# LLM Config Overrides
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-chat

# Backend Network Info
AXIS_API_BASE=http://localhost:8001
NEXT_PUBLIC_API_URL=http://localhost:8001
```

## Running the Application

The entire stack is containerized. Start the application using Docker Compose:

```bash
docker-compose up --build
```
*(Tip: Add `-d` to the command to run the containers in the background).*

### Local Dashboards

Once the containers successfully spin up, access your environments here:
- **Frontend App (Next.js UI)**: [http://localhost:3001](http://localhost:3001)
- **Backend API Base**: [http://localhost:8001](http://localhost:8001)
- **Interactive API Interface (Swagger)**: [http://localhost:8001/docs](http://localhost:8001/docs)

### Database Connection
- **Host**: `localhost` (Use `db` from within the internal Docker network)
- **Port**: `5433` (Mapped locally) / `5432` (Docker internal port)
- **Database Name**: `axis`
- **Username**: `axis_user`
- **Password**: `axis_dev_password`

## Project Structure

```text
axis/
├── agents/      # LLM orchestration, scheduler loops, swap and Python backend tools
├── backend/     # FastAPI app, SQLAlchemy DB models, and Pydantic schemas
├── configs/     # Organization-level JSON rule configs (e.g., hospitals.json)
├── db/          # SQL Init scripts and database seeding tasks
├── frontend/    # Next.js UI source code
└── docker-compose.yml 
```
