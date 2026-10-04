# HireLucent

> Bringing clarity and intelligence to candidate evaluation.

## Positioning Statement

An AI-powered recruitment and interview intelligence platform that helps hiring teams evaluate candidates through clear, evidence-backed assessments.

## Naming Rationale

**HireLucent** combines **"Hire,"** representing recruitment, with **"Lucent,"** meaning shining or giving light.

The name reflects the platform's purpose of bringing clarity to candidate evaluation by connecting CV analysis, interview insights and supporting evidence. It represents informed hiring decisions while keeping human judgment central.

## Running with Docker

**Prerequisites:** Docker Desktop (or Docker Engine with the Compose plugin).

1. Create your environment file and fill in the values:

```bash
   cp .env.example .env
```

2. Build and start everything:

```bash
   docker compose up --build -d
```

| Action | Command |
|---|---|
| Build and start | `docker compose up --build -d` |
| Check service status | `docker compose ps` |
| View logs | `docker compose logs -f backend` |
| Stop (data is kept) | `docker compose down` |
| Reset (deletes all data) | `docker compose down -v` |

The API is available at `http://localhost:8000` and its documentation at `http://localhost:8000/docs`.

**First start:** the embedding model (`qwen3-embedding:0.6b`, about 640 MB) is
downloaded automatically into a Docker volume. This needs an internet connection
and can take a few minutes. Later starts reuse the downloaded model.