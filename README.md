# HireLucent

> Bringing clarity and intelligence to candidate evaluation.

## Positioning Statement

An AI-powered recruitment and interview intelligence platform that helps hiring teams evaluate candidates through clear, evidence-backed assessments.

## Naming Rationale

**HireLucent** combines **"Hire,"** representing recruitment, with **"Lucent,"** meaning shining or giving light.

The name reflects the platform's purpose of bringing clarity to candidate evaluation by connecting CV analysis, interview insights and supporting evidence. It represents informed hiring decisions while keeping human judgment central.

**Core principle:** AI assists, people decide. Every score is traceable to evidence from the CV, and every external or consequential action (saving a job, publishing a post) waits for the interviewer's approval.

## Features

| Feature | Status |
|---|---|
| **F1** CV screening and semantic, requirement-based ranking with met / partially met / unmet evidence; candidates failing a must-have are excluded with the reason | Done |
| **F2** AI-based candidate scoring: 0–100 per dimension with justification, combined with an ATS-style match score | Done |
| **F3** Browser video interview between interviewer and candidate | Planned (Module 4) |
| **F4** Live, speaker-attributed, timestamped transcription | Planned (Module 5) |
| **F5** Interview Q&A analysis | Planned (Module 6) |
| **F6** Consolidated candidate assessment, comparison and export | Planned (Module 6) |
| **F7** (stretch) Candidate identification: interview PIN, face check when the candidate joins, and a profile panel in the interview room. See [Candidate identification and biometric data](#candidate-identification-and-biometric-data) | Done |
| **F8** (stretch) CV claim verification: every claim in the CV compared with what the candidate said in the interview, as contradiction, unverified, not discussed or consistent; points for the interviewer to check before deciding, never accusations. See [CV claim verification](#cv-claim-verification-f8) | Done |
| **F11** Innovation feature: **Candidate Feedback Composer**: every rejected or selected candidate gets a fair, evidence-based email, checked for fairness and approved by the interviewer before it is sent. See [Innovation Feature](#innovation-feature-candidate-feedback-composer-f11) | Done |

**What works today (pre-interview stage):**

1. **AI Agent for job creation.** The interviewer describes the role in a chat. The agent drafts the job description, using similar job description templates from the Knowledge Base as references when they exist. The interviewer approves or edits the draft.
2. **Requirements and weights.** The agent proposes a requirements checklist (must-have and preferred items with keywords, and a minimum experience) and scoring weights for technical skills, experience and qualifications. The interviewer confirms or edits them, then saves the job, which gets a code such as `HL-BE-01`.
3. **Publishing.** The agent asks for the job's Google Form, checks it, and after approval publishes the job to the HireLucent Careers blog.
4. **Fetch CVs.** CVs submitted through the Google Form are collected with one click, with progress and a reason for each CV that could not be collected.
5. **Screen CVs.** Each CV is read (with OCR for scanned PDFs), its facts are extracted, must-haves are checked, every requirement is matched by meaning with quoted CV evidence, and the candidate is scored and ranked.
6. **Review and shortlist.** Two rankings (requirement match and final score), filters and search, the evidence and score breakdown for each candidate, the reasons for every exclusion, and a shortlist made by the interviewer (one by one, top N or minimum score).
7. **Change the rules safely.** Requirements and weights can be edited after screening; saving resets the screening so every candidate is scored with the same rules.
8. **Knowledge Base.** Job description templates, reference documents and starter questions are uploaded once and reused.

## Architecture

The diagrams are in [`docs/`](docs):

- [High-level architecture](docs/High_Level_Architecture_30221_Farhan.drawio.pdf)
- [Detailed architecture](docs/Detailed_Architecture_30221_Farhan.drawio.pdf)
- LangGraph workflows: [1 Recruiter Agent](docs/LangGraph_1_Recruiter_Agent_Farahn_30221.drawio.pdf), [2 CV Screening](docs/LangGraph_2_CV_Screening_Farhan_30221.drawio.pdf), [3 Q&A Analysis](docs/LangGraph_3_QA_Analysis_30221_Farhan.pdf), [4 Final Assessment](docs/LangGraph_4_Final_Assessment_Farhan_30221.drawio.pdf), [5 Candidate Feedback](docs/LangGraph_5_Candidate_Feedback_30221_Farhan.pdf) (innovation feature)

The two architecture diagrams still show the original plan for job posting (LinkedIn/BdJobs) and email intake; they are updated before the final submission. LangGraph 2 shows the screening graph as built.

| Part | Technology | Role |
|---|---|---|
| Frontend | React 19, Vite, Tailwind CSS v4, served by nginx | Interviewer workspace |
| Backend | FastAPI, Pydantic v2, SQLAlchemy 2, Alembic | REST and WebSocket API, background tasks, role checks |
| AI workflows | LangGraph with PostgreSQL checkpoints | **Recruiter Agent** (chat, tools, human approval) and **CV Screening** graph (one branch per CV, at most 4 at a time) |
| LLM | Google Gemini 3.5 Flash-Lite (configurable; OpenAI supported) | Drafting, CV parsing, requirement matching, scoring |
| Embeddings | `qwen3-embedding:0.6b` on Ollama, in a local container | Knowledge Base search and CV matching |
| Vector store | ChromaDB | `jd_references`, `cv_embeddings`, `question_bank`, `rag_documents` |
| Database | PostgreSQL 16 | Jobs, candidates, screening results, conversations, tasks, checkpoints |
| MCP servers | Custom **RAG MCP** server; community **Blogger MCP** server | Knowledge Base search for the agent, and reference passages for checking interview answers; publishing job posts |
| OCR | Tesseract (through PyMuPDF) | Scanned CVs |

### LangGraph workflows built so far

- **Recruiter Agent** (`backend/app/graphs/recruiter/`): `load_context → agent → (call_tools | human_approval) → … → respond`. Read-only tools (Knowledge Base search) run directly; saving a job and publishing a post always pause for the interviewer's approval.
- **Candidate Feedback** (`backend/app/graphs/feedback/`, innovation feature F11): `load_evidence → (draft_feedback → check_fairness → review_email | use_template) → save_draft → human_review → send_email → record_sent`, with rewrites while a check fails (up to 3 tries), and edit, request changes, discard and Try again from the review. See [Innovation Feature](#innovation-feature-candidate-feedback-composer-f11).
- **Final Assessment** (`backend/app/graphs/final_assessment/`): `load_results → compute_scores → extract_claims → judge_claims → check_claims → save_claims → synthesize_report → check_traceability → save_draft → human_review → (save_assessment | synthesize_report | apply_edits)`. The claim nodes (F8) check the CV's claims before the report is written; **Check CV claims** and **Check again** run them alone. See [CV claim verification](#cv-claim-verification-f8).
- **CV Screening** (`backend/app/graphs/screening/`): `load_inputs →` one branch per CV: `extract_text → (run_ocr) → parse_cv → check_must_haves → (exclude_candidate | match_requirements → compute_ats_score → score_candidate → save_result)`, then `rank_candidates`. A CV that fails is recorded with its reason and never stops the batch. A run that is stopped or restarted continues from each CV's saved step.

### How a candidate is scored

| Score | How it is calculated |
|---|---|
| Requirement match (0–100) | Each requirement met = 1, partially met = 0.5, unmet = 0; must-haves count double |
| Dimension scores (0–100) | The AI scores technical skills, experience and qualifications from the matched evidence, each with a justification |
| Criteria score | Sum of each dimension score × its weight (the job's weights total 100%) |
| ATS score (0–100) | (Keyword coverage of the requirements + CV-to-job-description similarity) ÷ 2 |
| **Final score** | **0.8 × criteria score + 0.2 × ATS score**; ties go to the higher criteria score |

Candidates who miss a must-have, or have less than the minimum experience, are excluded and not scored. The reasons are saved and shown.

## Technology choices

- **FastAPI and Pydantic:** typed request and response models, validation, and automatic API documentation at `/docs`.
- **LangGraph:** real multi-step workflows with branching, human approval (`interrupt`), parallel branches (`Send`) and checkpoints in PostgreSQL, so work survives a restart.
- **MCP:** tools are separate services. The agent discovers the Knowledge Base search tool from the RAG MCP server. The same server's `verify_answer` tool, which finds approved reference passages for checking interview answers, is called only by the backend and is never offered to the agent. The Blogger MCP server is called only by the backend, after approval, so the AI can never publish on its own.
- **Gemini Flash-Lite:** a free tier that is fast enough for drafting and screening. The provider is a configuration switch.
- **Ollama embeddings:** run locally, so no CV text leaves the machine for embedding.
- **React, Vite and Tailwind CSS:**
  - React suits a screen-heavy app with live updates (chat, progress bars, and later the interview room).
  - Vite gives a fast development server and a small production build.
  - Tailwind CSS keeps the design consistent, because the colours, fonts, radius and shadows are defined once as design tokens.
- **nginx:** serves the built frontend and forwards `/api` to the backend, so the browser talks to one address.

## Prerequisites

- Docker Desktop (or Docker Engine with the Compose plugin)
- A Google Gemini API key
- An internet connection on the first start, to download the embedding model (about 640 MB)
- For publishing and CV collection only: a Google account, see [Google setup](#google-setup-publishing-and-cv-collection)
- For the one-time Google sign-in only: Python 3.11 on your own computer

## Setup and running

1. Create your environment file and fill in the values (see [Configuration](#configuration)):

   ```bash
   cp .env.example .env
   ```

2. Build and start everything with one command:

   ```bash
   docker compose up --build -d
   ```

| Action | Command |
|---|---|
| Build and start | `docker compose up --build -d` |
| Check service status | `docker compose ps` |
| View logs | `docker compose logs -f backend` |
| Restart one service | `docker compose restart backend` |
| Stop (data is kept) | `docker compose down` |
| Reset (deletes all data) | `docker compose down -v` |

| What | Address |
|---|---|
| Application | http://localhost:3000 |
| API documentation | http://localhost:8000/docs |

**On startup** the backend applies the database migrations and creates the first interviewer account from the `SEED_INTERVIEWER_*` values in `.env`. Sign in with that email and password.

**First start:** the embedding model is downloaded automatically into a Docker volume and can take a few minutes. Later starts reuse it.

**Sample job (optional):**

```bash
docker compose exec backend python -m scripts.seed --sample-data
```

**Sample Knowledge Base files:** `test-data/knowledge/backend_engineer_jd_template.txt` can be uploaded as a job description template, and `test-data/knowledge/backend_reference_notes.txt` (technical) and `test-data/knowledge/company_reference_notes.txt` (an invented company) as reference documents for checking the accuracy of interview answers.

## Configuration

All configuration comes from environment variables in `.env`. `.env.example` lists them with placeholder values; never commit `.env`.

| Variable | Purpose |
|---|---|
| `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`, `POSTGRES_HOST`, `POSTGRES_PORT` | Database connection |
| `JWT_SECRET`, `JWT_EXPIRE_MINUTES` | Signing key (at least 32 characters) and lifetime of sign-in tokens |
| `SEED_INTERVIEWER_EMAIL`, `SEED_INTERVIEWER_PASSWORD`, `SEED_INTERVIEWER_NAME` | The first interviewer account |
| `LLM_PROVIDER`, `LLM_MODEL`, `GEMINI_API_KEY`, `OPENAI_API_KEY` | Chat model (`gemini` or `openai`) |
| `LLM_REQUESTS_PER_MINUTE`, `AI_TIMEOUT_SECONDS` | Rate limit for the chat model and the timeout of each AI call |
| `EMBEDDING_PROVIDER`, `EMBEDDING_MODEL`, `OLLAMA_BASE_URL` | Embedding model |
| `CHROMA_HOST`, `CHROMA_PORT` | Vector store |
| `MCP_RAG_URL`, `JD_REFERENCE_MAX_DISTANCE`, `REFERENCE_MAX_DISTANCE` | RAG MCP server; how close a template must be to count as a reference, and how close a Knowledge Base reference passage must be to check an interview answer against it |
| `MCP_BLOGGER_URL`, `BLOGGER_BLOG_ID`, `BLOGGER_API_KEY` | Publishing to Blogger |
| `GOOGLE_TOKEN_FILE` | The Google sign-in file inside the backend container |
| `APP_ENV`, `LOG_LEVEL` | Environment name and log level |
| `PGADMIN_EMAIL`, `PGADMIN_PASSWORD` | Sign-in for the optional pgAdmin database viewer |
| `FACE_MODELS_DIR`, `MAX_PHOTO_MB` | Where the two face models are kept (downloaded when the backend image is built; default `models`) and the largest photo accepted (default 5 MB) |

## Usage walkthrough

1. **Sign in** at http://localhost:3000 with the seeded interviewer account.
2. **(Optional) Knowledge Base:** upload job description templates, so the agent can use them as references.
3. **Create a job:** on the Dashboard, type the role into "What role are you hiring for?". In the AI Agent conversation:
   - review the description and approve it, or ask for changes
   - review the requirements and weights, edit them if needed, then **Confirm and save job**
4. **Publish:** paste the job's Google Form link when the agent asks, review the post preview and approve it. The job appears on the careers blog.
5. **Candidates apply** through the form on the blog post.
6. **Applications tab:** press **Fetch CVs**. New applications waiting are also shown on the Dashboard.
7. **Screening tab:** press **Screen CVs** and follow the progress. Then:
   - compare the **Requirement match** and **Final ranking** views
   - open a candidate to see the evidence, scores, justifications and CV facts
   - shortlist candidates one by one, by top N or by minimum score
8. **Change the rules (if needed):** in the job brief, **Edit** the requirements and weights. If CVs were screened, confirm the reset, then press **Screen CVs** again. CVs are not read again.
9. **Feedback emails (innovation feature):** on the Screening tab, **Write emails** for the candidates not shortlisted, review them and send. After the interviews, decide **Hire** or **Reject** on the Assessments tab or the assessment's **Decision** tab, review the emails and send. See [Innovation Feature](#innovation-feature-candidate-feedback-composer-f11).

## External services and data

| Service | Used for | What is sent |
|---|---|---|
| Google Gemini API | Job descriptions, CV parsing, requirement matching, scoring, interview evaluation, CV claim check | Prompts with job details, **CV text** and **interview transcript text**, both with email addresses, phone numbers and links masked. They can still contain the candidate's name and other details written in the CV or said in the interview |
| Ollama (local container) | Embeddings | Nothing leaves the machine |
| Google Blogger API | Publishing approved job posts | The job title, description, job code and application form link |
| Google Forms and Drive APIs | Checking the application form and collecting CVs | Nothing is sent. Form responses and uploaded CVs are read |
| Gmail API (through the Google MCP server) | Sending feedback emails the interviewer approved (F11) | The candidate's email address, the subject and the approved text |

Prompts and model answers are never written to the logs.

## Privacy and data handling

- Only sample or synthetic CVs are used for development and demonstration. No personal data is stored in the repository.
- CV files are stored in a Docker volume (`/data/cv_intake`), never in the repository. `data/`, `sample_cvs/`, `secrets/`, `logs/` and `.env` are git-ignored.
- Logs contain IDs, counts and error types only: never names, email addresses, CV text, prompts, tokens or keys.
- Screening uses job-related criteria only.
- **Deleting a candidate** (`DELETE /candidates/{id}`, also a button on the Screening tab) removes their record, screening results, CV file and CV embeddings. The form response is remembered only by its ID, so it is not collected again.
- **Deleting a job** removes its candidates, CV files, embeddings and conversation.
- Raw interview audio and video will never be stored (planned for Modules 4–5).
- Candidate identification uses biometric data; how it is handled is described in the next section.

## Candidate identification and biometric data

Face data is the most sensitive data HireLucent handles (BID N17), so the check is built to keep as little as possible, for as short a time as possible, and never to decide anything on its own.

**What happens**

1. **Applying.** The job's Google Form asks for a recent passport-size photo (candidates are asked for one under 3 months old; its age cannot be checked) and a required consent: *"I agree that my photo is stored with my application and used only to confirm my identity at the interview. It is deleted when my application or the job is deleted."*
2. **Fetch CVs.** With consent, the photo is checked in memory (exactly one face, big, sharp and light enough). A usable photo is re-saved as a small JPEG (which drops the file's hidden camera, place and time details) and turned into a **face code**: 128 numbers made by the SFace model. Without consent nothing is read. A photo problem never stops the application; the reason is recorded instead.
3. **Interview PIN.** Each invitation has an 8-digit PIN right under the join link. Only its Argon2 hash is stored. Five wrong tries lock the link for 15 minutes; rescheduling or **Send a new PIN** gives a new link and PIN.
4. **Joining.** After the PIN and the consent on the pre-join page, a face guide (an oval with tips, run in the browser by MediaPipe and served by HireLucent itself) helps the candidate take **one photo**. The backend compares it with the invited candidate's face code and with the other applicants of the same job, then **discards it**. The candidate only sees "Thanks, you're all set".
5. **The result is for the interviewer only**, in the waiting row, the Admit bar and the room's Candidate info: *Identity verified* (match 0.50 or more), *Low match: check identity* (0.363 to 0.50), *Very low match: verify identity* (below 0.363), *Matches another applicant: verify identity*, or *Identity not checked* with the reason. The interviewer can open the application photo to compare it with the live video. The same panel shows the candidate's headline experience, key skills, pre-interview score and **Areas to probe** (requirements screening found only partly met or not met). **Nobody is ever blocked**: every candidate with the PIN can join, whatever the result. The limits come from a face-match test with the developer's own face (`backend/scripts/face_match_check.py`): the same person scored 0.58 to 0.63 against a passport photo, a different person 0.30; 0.363 is SFace's published same-person limit.

**What is stored, where and for how long**

| Data | Where | Kept until |
|---|---|---|
| Application photo (re-saved JPEG, random file name) | The `cv_data` Docker volume, next to the CVs | The candidate or the job is deleted |
| Face code (128 numbers) and the consent time | PostgreSQL, on the candidate | The candidate or the job is deleted |
| Identity result (label, match scores, reason, time) | PostgreSQL, on the interview | The candidate or the job is deleted |
| PIN | Only its Argon2 hash, on the interview | Replaced by the next PIN |
| Photo taken when joining, camera frames | **Never stored** | — |

**Who can see it.** Only signed-in interviewers. A candidate's pass gets 403 on every photo, score and report endpoint.

**Third parties.** None: both face models (OpenCV Zoo YuNet, MIT licence, and SFace, Apache 2.0) run on the local CPU in the backend container, and the browser model (MediaPipe BlazeFace, Apache 2.0) runs in the candidate's browser. No face ever goes to an external service. Google Drive only holds the photo the candidate uploaded to the form, like the CV.

**Logs** hold interview ids, the result label and the match score only.

## CV claim verification (F8)

After the interview, HireLucent compares every claim in the candidate's CV with what the candidate said, so the interviewer knows what to check before deciding. The workflow is part of [LangGraph 4](docs/LangGraph_4_Final_Assessment_Farhan_30221.drawio.pdf).

**Which claims.** Taken by code from the parsed CV: total years of experience, each job, each project, each certification, each education entry and each skill. The parsed CV holds job-related facts only, so nothing personal is compared. Each claim keeps its CV wording.

**The four results.**

| Result | Meaning |
|---|---|
| **Contradiction** | Something the candidate said clearly conflicts with the claim |
| **Unverified** | The claim came up, but the answer gave no detail that backs it up |
| **Not discussed** | Nothing the candidate said is about the claim |
| **Consistent** | Something the candidate said supports the claim |

**How it is checked.** The AI judges the claims in batches against the candidate's answers (contact details masked, no name). Code then checks each result: the quote must be in the candidate's answer to the question it names (with the same tolerance for speech-to-text spelling as the answer evaluation), contradictions and unverified claims need a short, neutral reason, and accusing words ("lie", "false", "dishonest" and similar) are refused. Failing claims are asked for again (up to 3 tries), then kept as *could not be checked*, so nothing unproven is shown. If the AI is not available, the claims are saved as *not checked* and the report is still written.

**Points to check, not accusations.** The results never change a score, the report, the label or the decision, and they never go into a feedback email. On the assessment page's **CV claims** tab (after Requirement coverage), each contradiction and unverified claim shows the CV wording, the question asked and the candidate's words (a link opens the transcript at that moment). The interviewer marks it **Checked** or **Dismissed**, with an optional note; who and when are recorded. Consistent claims are listed below them; claims nobody asked about are in a closed *Not discussed* section. Approving a report with an open contradiction shows a warning, never a block. The report PDF ends with section *C · CV claims to check*.

**When it runs.** Automatically, with **Evaluate** and **Evaluate again** (a new progress step, *Checking CV claims*). For an interview evaluated before F8, **Check CV claims** on the tab runs the claim check alone; **Check again** does the same when the AI was down. Neither touches the report, its approval or the decision.

**API** (interviewer only): `POST /interviews/{id}/assessment/claims` (check the claims alone, background task), `POST /interviews/{id}/assessment/claims/{claim_id}/review` (`checked`, `dismissed` or `reopen`, with an optional note). `GET /interviews/{id}/assessment` returns `claim_checks`; the ranked list returns `open_contradictions`. Migration `0017` adds `assessments.claim_checks`.

**Logs** hold ids, counts, result labels and problem codes only (`cv_claims_invalid`, `cv_claims_not_traced`, `cv_claims_checked`, `cv_claim_reviewed`), never CV or transcript text.

## Innovation Feature: Candidate Feedback Composer (F11)

> **This is HireLucent's innovation feature (BID §6).** The reasoning behind it is in [`docs/innovation_rationale.md`](docs/innovation_rationale.md), the design in [`docs/feedback_composer_design.md`](docs/feedback_composer_design.md) and the workflow in [LangGraph 5](docs/LangGraph_5_Candidate_Feedback_30221_Farhan.pdf).

**The problem.** Most applicants are rejected at screening and never hear why; interviewed candidates often get a generic message. Writing an honest, respectful answer for every candidate takes time, and a rushed one can say something unfair or untrue.

**What it does.** After the decision, HireLucent writes each candidate's email from their own saved evidence, checks it for fairness and waits for the interviewer:

| Who | Decision | Email | First draft by |
|---|---|---|---|
| Not shortlisted after screening (scored, or excluded for a missed must-have) | Rejected (automatic: everyone not shortlisted) | Strengths from the CV, led by the candidate's main area (CV summary, or their job titles), then the mandatory or preferred requirements not found in the CV | AI |
| CV could not be read | Rejected | A polite request to apply again with a readable CV | Fixed message |
| Interviewed, report approved | **Reject** | Strengths and growth areas from the approved report | AI |
| Interviewed, report approved | **Hire** | Selected for the role; the team will be in touch (no offer details) | Fixed message |

When there is nothing to praise, the email leaves the strengths out instead of inventing one. The greeting uses the name the candidate goes by ("Md. Tashsin Ahmed" and "TASHSIN AHMED" are both greeted as *Tashsin*).

The reason sentence follows the role's level: *"deliver in these areas from the very first day"* for experienced roles (3+ years), gentler wording for junior roles and internships.

**Fairness.** The wording is free: the AI writes in its own words, warm and encouraging, and may name the candidate's strengths or sum them up. There are no limits on how many points it uses and no exact-word matching. What it may not do is say anything unsafe or anything the candidate's results do not support. Every draft passes two checks before it is shown as ready:
1. **Safety rules (code):** no scores, ranks or percentages; no other candidates; no personal topics (age, gender, religion, health, family and similar); no personal data (email addresses, phone numbers, links); no promises; no offer details; no word-for-word quotes; no HTML or placeholders; and no named skill or tool that is in neither the candidate's results nor the job's requirements (for example *Kubernetes* when nothing about it was judged). A word that is part of the job's own requirements is allowed.
2. **AI review (meaning):** is it respectful and kind; does it say anything about the candidate that their points do not support (an invented skill, quality or achievement); is anything unfair by meaning (hints about personal traits, comparisons, promises). If the review cannot run, the draft shows **not checked**.
A draft that fails is rewritten (up to 3 tries). Anything still found stays on the draft as a **warning** that names the exact words and highlights them; the interviewer edits it, asks for changes, or sends it anyway after a confirm (the warning is kept with the email). The interviewer's own edits get the same checks, with warnings only; they are never rewritten.

**Human in the loop.** Nothing is sent without the interviewer. For each draft: **Approve and send**, **Edit** (checked again), **Request changes** with a note (the AI rewrites it), or **Discard**. **Send all passed** sends only drafts with no warnings, after a confirm. Sending goes through the Google MCP server's `send_email`, called only by the backend. If Google cannot be reached, the draft is kept as *Not sent* with **Try again**.

**Where it is in the app.**
- **Screening tab:** the final ranking shows each candidate's stage (Rejected, Shortlisted, Interview scheduled, Interviewed, Hired, Rejected after interview) and email; an email chip opens the **Feedback emails** sub-tab (next to Final ranking and Requirement match), which lists everyone rejected at screening with why, **Write emails**, **Send all passed** and a review panel. A decision made on the Assessments tab shows here too. Shortlisting stays possible until the email is sent; then it is locked.
- **Assessments tab:** **Decide by rule** (hire the top N, or everyone from a minimum overall score, and reject the rest), **Hire | Reject** on each row (only once the report is approved), the email status, and the same email buttons. The list fits a laptop screen without sideways scrolling; opening a row shows a short summary (score, two strengths and one weakness, what to check) with a link to the full report.
- **Assessment page → Decision tab** (after approval): the decision and the candidate's email, written straight away after the decision.
- The **Screening** and **Assessments** job tabs show *N emails to send* until everything is sent.

**Privacy.** The AI gets only job-related points with ids and the role level. It never gets the candidate's name (it writes `[first name]`, and the name is taken out of the CV summary), email address, scores, other candidates, transcript quotes, the identity check or the interviewer's note to themselves. The sent text, who approved it and when are stored with the candidate and deleted with the candidate or the job. Logs hold ids, kinds and warning codes only.

**API** (interviewer only): `PUT /candidates/{id}/decision`, `POST /jobs/{id}/decisions`, `GET /jobs/{id}/feedback`, `POST /jobs/{id}/feedback` (write), `POST /jobs/{id}/feedback/send`, `GET /candidates/{id}/feedback`, `POST /candidates/{id}/feedback/review`. Migration `0016` adds the `candidate_feedback` table.

**Future work.** Starting the emails from the AI Agent chat (an approval card in the conversation and a read-only email status tool for the agent).

## Google setup (publishing and CV collection)

Job posts are published to a Blogger page, and CVs arrive through a Google Form. Blogger is an openly declared stand-in for job portals such as LinkedIn and BdJobs, whose posting APIs are open to partners only. The rest of the application starts and works without this setup; only publishing and CV collection need it.

One-time setup with a personal Google account:

1. Create a Blogger blog and note its blog ID.
2. In a Google Cloud project, enable the Blogger, Google Forms and Google Drive APIs.
3. Set the OAuth consent screen to External and Testing, and add your own address as a test user.
4. Create an OAuth client of type Desktop app and save its JSON file as `secrets/google_client.json`.
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

**The application form** needs five questions: the applicant's full name, email address, a CV file upload (PDF or DOCX), a required photo upload whose title contains "photo" (JPG or PNG, a recent passport-size photo) and a required consent checkbox whose title contains "consent" (the text is in [Candidate identification and biometric data](#candidate-identification-and-biometric-data)). Publishing is refused until the photo and consent questions are there. Each job uses its own form. To check a form without saving anything:

```bash
docker compose exec backend python -m scripts.form_check "<form link>"
```

The `secrets/` folder is git-ignored and must never be committed. While the consent screen is in Testing mode a sign-in lasts about 7 days. Run step 7 again when publishing or CV collection stops working, and before a demo, then restart the Blogger server:

```bash
docker compose restart mcp-blogger
```

The `mcp-blogger` service runs the community [blogger-mcp-server](https://github.com/zachsladecode/blogger-mcp-server) (MIT licence), pinned to one commit, behind an HTTP bridge. The application only ever calls its create-post tool, and only after the interviewer approves the post.

## Development

**Backend tests** (in a local virtual environment):

```bash
cd backend
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
pytest -q
```

**Frontend checks:**

```bash
cd frontend
npm install
npm run lint
npm run build
```

**Database viewer (optional):** pgAdmin runs only when asked for, so the normal start is unchanged:

```bash
docker compose --profile tools up -d pgadmin
```

Open http://localhost:5050 (only from this computer), sign in with `PGADMIN_EMAIL` and `PGADMIN_PASSWORD` from `.env`, then open **Servers › HireLucent** and enter `POSTGRES_PASSWORD`. The connection uses the default database user `hirelucent`; if `POSTGRES_USER` is changed, change it in `pgadmin/servers.json` too. Stop it with `docker compose stop pgadmin`. It shows real candidate data, so use it only on your own machine.

**Score stability check:** scores one already-screened candidate again 1–5 times, without saving, and compares the results with the saved scores. It prints IDs and numbers only:

```bash
docker compose exec backend python -m scripts.stability_check --candidate <id> --runs 3
```

**Project layout:**

```
backend/
  app/
    api/routes/     REST and WebSocket endpoints
    services/       business logic (jobs, chat, intake, screening, shortlist, knowledge, tasks)
    graphs/         LangGraph workflows (recruiter/, screening/)
    ai/             AI model access: rate limit, retries, timeouts
    rag/            ChromaDB access, chunking, MCP client
    mcp_servers/    the custom RAG MCP server
    models/ schemas/ core/ db/
  alembic/          database migrations
  scripts/          seed, Google sign-in and check scripts
  tests/
frontend/src/       pages, components, hooks, lib
mcp-blogger/        container for the community Blogger MCP server
docs/               architecture and LangGraph diagrams
```

**Branches:** `main` (final release), `dev` (completed modules) and one branch per module, merged into `dev` by pull request.

## Known limitations

- **Identity check (F7):** there is no liveness check yet, so a clear printed photo held up to the camera could pass; the interviewer still sees the live video and the label is advice only. Twins and close look-alikes can match each other. An old or poor application photo gives a lower score (the label then asks the interviewer to compare). Interviews scheduled before F7 have no PIN and no check. The photo inside a CV is not used.

- **CV claim check (F8):** the AI may judge a claim imperfectly (for example unverified where a person would say consistent); every result shows its evidence and the interviewer decides. A claim mentioned only in an answer whose question was lost from the transcript is not compared.

- **Score repeatability:** the model in use (Gemini 3.5 Flash-Lite) ignores the temperature setting, so scoring the same CV again can differ slightly. Measured on one candidate over 3 runs: requirement results, match and ATS scores were identical; the largest final-score difference was 2 points.
- **Screening speed:** limited by the free-tier LLM rate (15 requests per minute by default; about 3 calls per CV). The time for 20 CVs is still to be measured and will be stated here.
- **Google sign-in** expires after about 7 days while the consent screen is in Testing mode.
- **New applications count:** the "waiting" number compares the form's total responses with those already seen, so it can be wrong after responses are deleted from the form.
- **CV intake** is through Google Forms only; email intake is not built.
- **English only**, for CVs and interviews.
- On phones, the sidebar takes a lot of space at the top of the screen.
