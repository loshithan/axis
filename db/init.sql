-- AXIS Database Initialization
-- Creates tables, indexes, and enables pgvector extension

-- Enable extensions
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ── Enums ──
CREATE TYPE shift_status AS ENUM ('proposed', 'confirmed', 'cancelled', 'swapped', 'open');
CREATE TYPE leave_status AS ENUM ('pending', 'approved', 'rejected', 'covered');
CREATE TYPE escalation_status AS ENUM ('open', 'resolved', 'dismissed');

-- ── Core Tables ──

CREATE TABLE sbus (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE,
    code VARCHAR(20) NOT NULL UNIQUE,
    timezone VARCHAR(50) DEFAULT 'Asia/Colombo',
    config JSONB NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE departments (
    id SERIAL PRIMARY KEY,
    sbu_id INTEGER NOT NULL REFERENCES sbus(id),
    name VARCHAR(100) NOT NULL,
    code VARCHAR(50) NOT NULL,
    UNIQUE(sbu_id, code)
);

CREATE TABLE shift_types (
    id SERIAL PRIMARY KEY,
    sbu_id INTEGER NOT NULL REFERENCES sbus(id),
    name VARCHAR(100) NOT NULL,
    code VARCHAR(50) NOT NULL,
    start_time TIME NOT NULL,
    end_time TIME NOT NULL,
    required_certifications JSONB DEFAULT '[]',
    min_headcount INTEGER DEFAULT 1,
    department_code VARCHAR(50) NOT NULL,
    UNIQUE(sbu_id, code)
);

CREATE TABLE workers (
    id SERIAL PRIMARY KEY,
    employee_id VARCHAR(50) NOT NULL UNIQUE,
    name VARCHAR(200) NOT NULL,
    email VARCHAR(200),
    phone VARCHAR(20),
    department_id INTEGER NOT NULL REFERENCES departments(id),
    certifications JSONB DEFAULT '[]',
    max_weekly_hours FLOAT DEFAULT 40.0,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE availability (
    id SERIAL PRIMARY KEY,
    worker_id INTEGER NOT NULL REFERENCES workers(id),
    date DATE NOT NULL,
    start_time TIME NOT NULL,
    end_time TIME NOT NULL,
    is_available BOOLEAN DEFAULT TRUE,
    UNIQUE(worker_id, date, start_time)
);

CREATE TABLE shifts (
    id SERIAL PRIMARY KEY,
    worker_id INTEGER REFERENCES workers(id),
    shift_type_id INTEGER NOT NULL REFERENCES shift_types(id),
    date DATE NOT NULL,
    start_time TIME NOT NULL,
    end_time TIME NOT NULL,
    status shift_status DEFAULT 'proposed',
    fairness_score FLOAT,
    explanation TEXT,
    reasoning_trace JSONB,
    created_by VARCHAR(50) DEFAULT 'agent',
    created_at TIMESTAMP DEFAULT NOW(),
    confirmed_at TIMESTAMP,
    UNIQUE(worker_id, date, start_time)
);

CREATE TABLE leave_requests (
    id SERIAL PRIMARY KEY,
    worker_id INTEGER NOT NULL REFERENCES workers(id),
    shift_id INTEGER REFERENCES shifts(id),
    date DATE NOT NULL,
    reason TEXT,
    status leave_status DEFAULT 'pending',
    replacement_worker_id INTEGER REFERENCES workers(id),
    resolution_summary TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    resolved_at TIMESTAMP
);

CREATE TABLE escalations (
    id SERIAL PRIMARY KEY,
    shift_type_id INTEGER REFERENCES shift_types(id),
    date DATE NOT NULL,
    description TEXT NOT NULL,
    agent_reasoning TEXT NOT NULL,
    status escalation_status DEFAULT 'open',
    resolved_by VARCHAR(200),
    created_at TIMESTAMP DEFAULT NOW(),
    resolved_at TIMESTAMP
);

CREATE TABLE agent_logs (
    id SERIAL PRIMARY KEY,
    agent_name VARCHAR(50) NOT NULL,
    session_id VARCHAR(100) NOT NULL,
    input_message TEXT,
    reasoning_steps JSONB,
    tools_called JSONB,
    output JSONB,
    duration_ms INTEGER,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Agent memory layer (pgvector)
CREATE TABLE agent_memory (
    id SERIAL PRIMARY KEY,
    session_id VARCHAR(100) NOT NULL,
    sbu_code VARCHAR(20) NOT NULL,
    content TEXT NOT NULL,
    embedding vector(1536),
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT NOW()
);

-- ── Indexes ──
CREATE INDEX idx_shifts_worker_date ON shifts(worker_id, date);
CREATE INDEX idx_shifts_date_status ON shifts(date, status);
CREATE INDEX idx_shifts_shift_type ON shifts(shift_type_id, date);
CREATE INDEX idx_availability_worker_date ON availability(worker_id, date);
CREATE INDEX idx_leave_requests_worker ON leave_requests(worker_id, status);
CREATE INDEX idx_leave_requests_date ON leave_requests(date, status);
CREATE INDEX idx_escalations_status ON escalations(status, date);
CREATE INDEX idx_agent_logs_session ON agent_logs(session_id);
CREATE INDEX idx_agent_logs_agent ON agent_logs(agent_name, created_at);
CREATE INDEX idx_agent_memory_embedding ON agent_memory USING ivfflat (embedding vector_cosine_ops);
