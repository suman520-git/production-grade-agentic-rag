# Production-Grade Agentic RAG Capstone

A document question-answering application using OpenAI, LangChain,
LangGraph, FastAPI, Streamlit, PostgreSQL, and Qdrant.

## Features

- Document creation and UTF-8 TXT uploads
- PostgreSQL document and chunk storage
- OpenAI embeddings stored in Qdrant
- Category and document filters
- Hybrid vector and keyword retrieval
- Reciprocal Rank Fusion and LLM reranking
- Document relevance grading
- Bounded query rewriting
- Answers with citations and source text
- Grounding and answer-responsiveness checks
- Abstention when evidence is insufficient
- API-key authentication and request validation
- Rate limiting and configured CORS
- Keyword fallback during vector-retrieval failures
- Request IDs, stage timings, and structured logs
- Storage readiness checks
- A 50-question development evaluation and report

## Requirements

- Docker Desktop with Linux containers and Docker Compose
- An OpenAI API key with available API usage
- Free local ports: 8000, 8502, 5434, and 6333

Python 3.11 is needed only for running scripts directly on the host.

## Configuration

Copy the example configuration:

```powershell
Copy-Item .env.example .env
```

Edit `.env` and set:

- `POSTGRES_PASSWORD`
- `OPENAI_API_KEY`
- `APP_API_KEY`

Generate a random password or application key with Python:

```powershell
python -c "import secrets; print(secrets.token_hex(32))"
```

Run it separately for each secret. Never commit `.env`.

When using an existing PostgreSQL volume, retain its existing
database credentials.

## Start the application

```powershell
docker compose up --build
```

For background execution:

```powershell
docker compose up -d --build
```

Open:

- Streamlit: http://127.0.0.1:8502
- FastAPI Swagger: http://127.0.0.1:8000/docs

Enter APP_API_KEY in Streamlit or Swagger's Authorize dialog.

A new installation initializes empty database tables and a Qdrant
collection. Upload documents before asking document questions.
Existing compatible storage is reused.

## Container networking

| Caller | Destination |
|---|---|
| Browser | localhost:8502 for Streamlit |
| Browser | localhost:8000 for FastAPI |
| Streamlit container | backend:8000 |
| FastAPI container | postgres:5432 |
| FastAPI container | qdrant:6333 |
| Windows database scripts | localhost:5434 |
| Windows vector scripts | localhost:6333 |

Database host ports are bound to localhost for local development.

## Basic verification

```powershell
docker compose ps
docker compose logs --tail 60 backend
```

In Swagger:

1. Authorize with APP_API_KEY.
2. Execute GET /ready.
3. Confirm PostgreSQL and Qdrant both report ready.
4. Upload a TXT document.
5. Ask a question about that document in Streamlit.
6. Expand the cited source.

GET /health checks that the API is running.
GET /ready checks the required storage.
Readiness does not call OpenAI.

## Stop and restart

```powershell
docker compose stop
docker compose start
```

To remove containers and the Compose network while retaining named volumes:

```powershell
docker compose down
```

Do not add `-v` unless you intentionally want to delete stored data.

## Evaluation

The dataset contains 50 development questions covering:

- Annual leave
- Remote work
- Training budget
- Missing evidence
- Filter exclusion
- Greeting routing

See [the evaluation report](docs/evaluation_report.md).

Recorded automated pass rates: 94%, 98%, and 100%.
The final run passed 50/50 cases.

These are development regression results, not independent held-out
accuracy or a guarantee of production performance.

To run evaluation scripts on Windows, activate the project virtual
environment, install requirements, and keep Docker services running:

```powershell
python -m pip install -r requirements.txt
python run_evaluation.py
python inspect_evaluation_failures.py
python generate_evaluation_report.py
```

Evaluation makes paid OpenAI calls. Dataset document IDs and content
must match the local database. Review reference policies and labels
before generating a dataset for a different installation.

Raw evaluation runs are saved locally under `evaluations/`.

## Dependencies

- `requirements.txt`: pinned application dependencies used for builds
- `docs/container-dependencies.txt`: snapshot of installed container packages

## Current limitations

- TXT ingestion only
- Shared application API key; no individual user accounts
- In-memory rate limiting; one backend worker
- LLM relevance and grounding judgments can be incorrect
- Small development evaluation using three reference policies
- Startup initialization is not a general schema migration system
- Local HTTP deployment; AWS deployment is a separate manual step

## Deployment status

Manual AWS deployment is pending.
AWS application and API documentation links will be added after
deployment and verification.


## Project documentation

- [Architecture](docs/architecture.md)
- [Database schema](docs/database_schema.md)
- [SQL schema export](docs/database_schema.sql)
- [Evaluation report](docs/evaluation_report.md)

- [Submission details](docs/submission.md)