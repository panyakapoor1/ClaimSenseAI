# ClaimSense AI

A Multi-Agent RAG-Based Explainable Insurance Claim Auditor for Indian Healthcare Claims.

## Problem Statement

In India, health insurance claims are opaque and difficult to understand. Patients frequently face unexpected partial settlements, room-rent deductions, consumable exclusions, and hidden policy limits. 

Most patients cannot read through a dense 50+ page policy document or verify whether their Third Party Administrator (TPA) has unfairly rejected a claim. ClaimSense AI acts as an autonomous, multi-agent advocate that reads hospital bills, correlates them against complex policy documents using RAG, and generates an item-by-item explainable audit report alongside an automated appeal letter.

## Features

* OCR Bill Extraction
* Policy Parsing
* RAG Retrieval
* Multi-Agent Pipeline
* Claim Auditing
* Explainable AI
* Appeal Generation
* Real-Time Updates

## Architecture Diagram

The system employs an event-driven, asynchronous microservice architecture to decouple web requests from heavy AI workloads.

```mermaid
graph TD
    Client[Next.js Client] -->|REST / WebSockets| API(FastAPI Server)
    API -->|Synchronous CRUD| DB[(PostgreSQL + pgvector)]
    API -->|Enqueue Task| Redis[(Redis Broker)]
    
    subgraph Background Workers
        Worker[ARQ Worker Process]
    end
    
    Redis -->|Dequeue Task| Worker
    Worker -->|Fetch Data| DB
    Worker -->|Write Results| DB
    Worker -.->|API Calls| LLM((Groq Llama-3))
    Worker -.->|OCR/Embeddings| LocalAI((Local Models))
```

## System Design

The system utilizes a containerized, asynchronous microservice architecture. 

1. **Frontend:** A Next.js 15 client dashboard.
2. **API Layer:** FastAPI exposing REST endpoints and WebSockets for real-time progress tracking.
3. **Async Queue:** Redis and ARQ offload heavy AI tasks (OCR, embedding generation, LLM reasoning) from the main API thread.
4. **Data Layer:** PostgreSQL stores structured application data (Users, Claims), while the pgvector extension natively stores and queries policy embeddings in the exact same database, eliminating distributed transaction risks.

## Tech Stack

**Frontend**
* Next.js 15 (App Router)
* TypeScript
* Tailwind CSS
* shadcn/ui

**Backend**
* FastAPI (Python 3.11)
* ARQ (Async Redis Queue)
* SQLAlchemy (Asyncpg)

**Database**
* PostgreSQL
* pgvector
* Redis (Message Broker & Cache)

**AI Layer**
* Groq API (Llama-3-70B for fast, free reasoning)
* local sentence-transformers (Embeddings)
* pdfplumber (OCR)

**Infrastructure**
* Docker & Docker Compose

## Folder Structure

`	ext
ClaimSenseAI/
├── backend/
│   ├── main.py
│   ├── requirements.txt
│   ├── Dockerfile
│   ├── .env.example
│   └── .dockerignore
├── docker-compose.yml
├── .gitignore
└── README.md
`

## Local Development Setup

ClaimSense AI uses Docker Compose to guarantee environmental consistency. 

### Prerequisites
* Docker Desktop installed and running.
* Git.

### 1. Clone the repository
`ash
git clone https://github.com/panyakapoor1/ClaimSenseAI.git
cd ClaimSenseAI
`

### 2. Configure Environment Variables
Copy the example environment file:
`ash
cp backend/.env.example backend/.env
`
*(Add your Groq API key to the .env file).*

### 3. Start the Infrastructure
Build and start the PostgreSQL, Redis, and FastAPI containers:
`ash
docker compose up -d --build
`

The API will be available at http://localhost:8000. You can view the interactive Swagger documentation at http://localhost:8000/docs.

## Environment Variables

| Variable | Description |
|---|---|
| DATABASE_URL | The async connection string to the PostgreSQL database. |
| REDIS_URL | The connection string for the ARQ queue broker. |
| GROQ_API_KEY | API key for Llama-3 inference. |

## Database Schema
The application uses PostgreSQL as its primary datastore, leveraging the `pgvector` extension to fuse relational data with AI embeddings.

```mermaid
erDiagram
    USERS ||--o{ POLICIES : owns
    USERS ||--o{ CLAIMS : submits
    POLICIES ||--o{ POLICY_CHUNKS : contains
    CLAIMS ||--o{ CLAIM_ITEMS : has
    CLAIM_ITEMS ||--o| AUDIT_FINDINGS : results_in

    USERS {
        uuid id PK
        string email
        datetime created_at
    }
    
    POLICIES {
        uuid id PK
        uuid user_id FK
        string insurer_name
        string policy_name
        datetime created_at
    }
    
    POLICY_CHUNKS {
        uuid id PK
        uuid policy_id FK
        string page_number
        string section_header
        text text_content
        vector embedding
    }
    
    CLAIMS {
        uuid id PK
        uuid user_id FK
        float total_billed
        string status
        datetime created_at
    }
    
    CLAIM_ITEMS {
        uuid id PK
        uuid claim_id FK
        string category
        string description
        float billed_amount
        float allowed_amount
    }
    
    AUDIT_FINDINGS {
        uuid id PK
        uuid claim_item_id FK
        string status
        string reason
        string policy_clause_cited
        string original_clause_text
        string page_number
        float confidence
        datetime created_at
    }
```

## API Documentation
*(Coming Soon)*

## Agent Architecture
*(Coming Soon)*

## RAG Pipeline
*(Coming Soon)*

## Screenshots
*(Coming Soon)*

## Performance Metrics
*(Coming Soon)*

## Future Roadmap
*(Coming Soon)*
