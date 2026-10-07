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
| Google Blogger API | Publishing approved job posts | The job title, description, job code and application form link |
| Google Forms and Drive APIs | Checking the application form and collecting CVs | Nothing is sent. Form responses and uploaded CVs are read. |

The provider and model are set in `.env` (`LLM_PROVIDER`, `LLM_MODEL`,
`EMBEDDING_PROVIDER`, `EMBEDDING_MODEL`). Prompts and model answers are never
written to the logs.

## Google setup (publishing and CV collection)

Job posts are published to a Blogger page, and CVs arrive through a Google
Form. Blogger is an openly declared stand-in for job portals such as LinkedIn
and BdJobs, whose posting APIs are open to partners only. The rest of the
application starts and works without this setup; only publishing and CV
collection need it.

One-time setup with a personal Google account:

1. Create a Blogger blog and note its blog ID.
2. In a Google Cloud project, enable the Blogger, Google Forms and Google
   Drive APIs.
3. Set the OAuth consent screen to External and Testing, and add your own
   address as a test user.
4. Create an OAuth client of type Desktop app and save its JSON file as
   `secrets/google_client.json`.
5. Create an API key restricted to the Blogger API.
6. Set `BLOGGER_BLOG_ID` and `BLOGGER_API_KEY` in `.env`.
7. Sign in once, on your own computer (it opens a browser):

   ```bash
   cd backend
   python -m scripts.google_auth
   ```

   This saves `secrets/google_token.json` and `secrets/blogger_tokens.json`.
8. Start the application and check the connection. Nothing is published:

   ```bash
   docker compose up -d --build
   docker compose exec backend python -m scripts.blogger_check
   ```

The `secrets/` folder is git-ignored and must never be committed. While the
consent screen is in Testing mode a sign-in lasts about 7 days, so run step 7
again when publishing stops working, and before a demo.

The `mcp-blogger` service runs the community
[blogger-mcp-server](https://github.com/zachsladecode/blogger-mcp-server)
(MIT licence), pinned to one commit, behind an HTTP bridge. The application
only ever calls its create-post tool, and only after the interviewer approves
the post.
