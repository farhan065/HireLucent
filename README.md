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

| What | Address |
|---|---|
| Application | http://localhost:3000 |
| API documentation | http://localhost:8000/docs |

**First start:** the embedding model (`qwen3-embedding:0.6b`, about 640 MB) is
downloaded automatically into a Docker volume. This needs an internet connection
and can take a few minutes. Later starts reuse the downloaded model.

**First interviewer account:** created automatically at startup from the
`SEED_INTERVIEWER_*` values in `.env`.

**Sample job (optional):**

```bash
docker compose exec backend python -m scripts.seed --sample-data
```

## Frontend

The interface is built with **React**, **Vite** and **Tailwind CSS**.

- **React** suits a screen-heavy application with live updates, such as chat,
  progress indicators and the interview room, and has mature libraries for
  video (LiveKit) that the interview stage needs.
- **Vite** gives a fast development server and a small production build.
- **Tailwind CSS** keeps the design consistent: the colours, fonts, radius and
  shadows are defined once as design tokens and reused on every screen.

In Docker, the built files are served by **nginx**, which also forwards `/api`
requests to the backend, so the browser talks to a single address.

## External services and data

| Service | Used for | What is sent |
|---|---|---|
| Google Gemini API | Text generation and analysis | Prompts, which will include job descriptions, CV text and interview transcripts |
| Ollama (local container) | Embeddings | Nothing leaves the machine |

The provider and model are set in `.env` (`LLM_PROVIDER`, `LLM_MODEL`,
`EMBEDDING_PROVIDER`, `EMBEDDING_MODEL`). Prompts and model answers are never
written to the logs.