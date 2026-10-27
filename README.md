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
| **F9** (stretch) Comprehensive interview scoring: an interview performance score, separate from the CV score, from six dimensions (technical competency, communication, relevance, problem-solving, depth of experience, alignment with the job's requirements), each 0–100 with the answers or requirements behind it. See [Interview performance scoring](#interview-performance-scoring-f9) | Done |
| **F10** (stretch) Interview quality assessment: how the interview itself was run, not the candidate: a quality score from the interviewer's questions, the coverage of the job's requirements and the speaking time, actionable recommendations for the next interview, and a comparison of how consistently the job's candidates were interviewed. See [Interview quality assessment](#interview-quality-assessment-f10) | Done |
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
- LangGraph workflows: [1 Recruiter Agent](docs/LangGraph_1_Recruiter_Agent_Farhan_30221.drawio.pdf), [2 CV Screening](docs/LangGraph_2_CV_Screening_Farhan_30221.drawio.pdf), [3 Q&A Analysis](docs/LangGraph_3_QA_Analysis_30221_Farhan.pdf), [4 Final Assessment](docs/LangGraph_4_Final_Assessment_Farhan_30221.drawio.pdf), [5 Candidate Feedback](docs/LangGraph_5_Candidate_Feedback_30221_Farhan.pdf) (innovation feature), [6 Interview Quality](docs/LangGraph_6_Interview_Quality_30221_Farhan.pdf)

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
- **Final Assessment** (`backend/app/graphs/final_assessment/`): `load_results → score_dimensions → compute_scores → extract_claims → judge_claims → check_claims → save_claims → synthesize_report → check_traceability → save_draft → human_review → (save_assessment | synthesize_report | apply_edits)`. `score_dimensions` (F9) works out the six interview performance dimensions and the interview score by rule; see [Interview performance scoring](#interview-performance-scoring-f9). The claim nodes (F8) check the CV's claims before the report is written; **Check CV claims** and **Check again** run them alone. See [CV claim verification](#cv-claim-verification-f8).
- **Interview Quality** (`backend/app/graphs/interview_quality/`, F10): `load_interview → measure_interview → score_quality → find_issues → (write_recommendations → check_recommendations | save_quality) → save_quality`, with the recommendations asked for again while one cannot be proven (up to 3 tries). It runs after the report and on its own (**Check interview quality**). See [Interview quality assessment](#interview-quality-assessment-f10).
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
| `AI_PRICE_INPUT_PER_1M`, `AI_PRICE_OUTPUT_PER_1M` | The chat model's price in US dollars per million input and output tokens, for the [AI cost report](#ai-cost-report) |
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
| Google Gemini API | Job descriptions, CV parsing, requirement matching, scoring, interview evaluation, the interview report, CV claim check, interview quality recommendations, feedback emails | Prompts with job details, **CV text** and **interview transcript text**, both with email addresses, phone numbers and links masked. They can still contain the candidate's name and other details written in the CV or said in the interview. The interview quality and feedback prompts get no name (see their sections) |
| Deepgram (default speech-to-text) | Live interview transcription | The interviewer's and the candidate's **interview audio**, streamed during the interview. Deepgram is asked not to keep it for model training (`mip_opt_out=true`) |
| AssemblyAI (optional speech-to-text, `STT_PROVIDER=assemblyai`) | Live interview transcription | The same **interview audio**. Its free plan cannot opt out of model training, so it is used with test interviews only |
| Ollama (local container) | Embeddings | Nothing leaves the machine |
| Google Blogger API | Publishing approved job posts | The job title, description, job code and application form link |
| Google Forms and Drive APIs | Checking the application form and collecting CVs | Nothing is sent. Form responses and uploaded CVs are read |
| Google Calendar API (through the Google MCP server) | Interview invitations, updates and cancellations the interviewer approved | The candidate's name and email address, the job title, the time, the join link and the interview PIN |
| Gmail API (through the Google MCP server) | Sending feedback emails the interviewer approved (F11) | The candidate's email address, the subject and the approved text |

Prompts and model answers are never written to the logs.

## Privacy and data handling

- Only sample or synthetic CVs are used for development and demonstration. No personal data is stored in the repository.
- CV files are stored in a Docker volume (`/data/cv_intake`), never in the repository. `data/`, `sample_cvs/`, `secrets/`, `logs/` and `.env` are git-ignored.
- Logs contain IDs, counts and error types only: never names, email addresses, CV text, prompts, tokens or keys.
- Screening and every assessment use job-related criteria only (see [Fairness](#fairness)).
- **Deleting a candidate** (`DELETE /candidates/{id}`, also a button on the Screening tab) removes their record, screening results, CV file and CV embeddings, application photo and face code, interviews with their transcripts, assessments and CV claim and interview quality results, feedback email, and the AI workflows' saved state for them (LangGraph checkpoints of the room chat, Q&A analysis, report, CV claim check, interview quality check and feedback email). The form response is remembered only by its ID, so it is not collected again. A candidate with an upcoming or running interview cannot be deleted until the interview is cancelled, because they still hold a calendar invitation and a join link.
- **Deleting a job** removes all of that for each of its candidates, plus the job's conversation and screening runs.
- **AI working state is not kept longer than needed.** A Q&A analysis run's saved state (which holds the transcript and the answers) is deleted as soon as the run ends, because its results are saved in the assessment. The report's and the feedback email's state is kept while they wait for the interviewer's review, and deleted with the candidate or the job.
- **Raw interview audio and video are never stored.** Audio is streamed to the speech-to-text provider during the interview and only the transcript text is saved; the live text messages between interviewer and candidate are not saved either.
- **Transport security.** Calls to Gemini, Google, Deepgram and AssemblyAI use HTTPS or secure WebSockets (WSS). The app itself runs locally over plain HTTP (`http://localhost:3000`) and LiveKit over `ws://localhost:7880`, which is accepted for a local-only setup; a deployment would put both behind HTTPS/WSS.
- Candidate identification uses biometric data; how it is handled is described in the next section.

## Fairness

HireLucent scores candidates on job-related evidence only (BID N20). The rules are built into the AI steps and checked by tests:

- **Criteria come from the job.** Screening scores each requirement of the job (technical skills, experience, qualifications) with the interviewer's confirmed weights; the interview is judged on its answers and the job's requirements. Nothing else is scored.
- **Personal traits are excluded.** Every AI step that judges a candidate (requirement matching, CV scoring, answer evaluation, the report, the CV claim check, interview quality recommendations and the feedback email and its review) is told never to consider age, gender, nationality, religion, accent or any other personal trait. CV reading is told not to extract age, date of birth, gender, nationality, religion, marital status or a photo.
- **Personal data stays out of the inputs.** Email addresses, phone numbers and links are masked in every CV and transcript text sent to the AI. The candidate's name, application photo, face code and identity check result are never part of a scoring prompt; the identity check never changes a score.
- **Every conclusion shows its evidence** (a CV quote, a transcript quote or a requirement), and a person approves every report, decision and email.
- `backend/tests/test_fairness.py` checks these rules: the instruction is present in every judging prompt, and the inputs built for screening, matching, the interview steps and the CV claim check carry no contact details or personal fields.

**Limits.** The CV and transcript text can still contain the candidate's name and anything else they wrote or said (for example a photo caption, an age or a hobby), so the AI may see it even though it is told to ignore it. The AI can still make biased or wrong judgements; the evidence shown with each score and the human review are there to catch them. Communication is judged on clarity and structure, never on accent, but speech-to-text errors can still make an answer read worse than it was said. There is no statistical fairness audit across groups, because the project uses synthetic candidates only.

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

After an interview, the growth areas are named as the broader skill area they belong to (for example *core machine learning fundamentals*), never the specific question or concept that was asked, so the interview questions stay with the team.

The sentence on why the growth areas matter is written by the AI in its own words from the job's requirements, never with invented duties. Its meaning follows the role's level: needed *"from the very first day"* for experienced roles (3+ years), gentler for junior roles and internships. Preferred requirements missed at screening are described as making an application stronger, never as a need.

**Fairness.** The wording is free: the AI writes in its own words, warm and encouraging, and may name the candidate's strengths or sum them up. There are no limits on how many points it uses and no exact-word matching. What it may not do is say anything unsafe or anything the candidate's results do not support. Every draft passes two checks before it is shown as ready:
1. **Safety rules (code):** no scores, ranks or percentages; no other candidates; no personal topics (age, gender, religion, health, family and similar); no personal data (email addresses, phone numbers, links); no promises; no offer details; no word-for-word quotes; no HTML or placeholders; and no named skill or tool that is in neither the candidate's results nor the job's requirements (for example *Kubernetes* when nothing about it was judged). A word that is part of the job's own requirements is allowed.
2. **AI review (meaning):** is it respectful and kind; does it say anything about the candidate that their points do not support (an invented skill, quality or achievement); is anything unfair by meaning (hints about personal traits, comparisons, promises). If the review cannot run, the draft shows **not checked**.
A draft that fails is rewritten (up to 3 tries). Anything still found stays on the draft as a **warning** that names the exact words and highlights them; the interviewer edits it, asks for changes, or sends it anyway after a confirm (the warning is kept with the email). The interviewer's own edits get the same checks, with warnings only; they are never rewritten.

**Human in the loop.** Nothing is sent without the interviewer. For each draft: **Approve and send**, **Edit** (checked again), **Request changes** with a note (the AI rewrites it), or **Discard**. **Send all passed** sends only drafts with no warnings, after a confirm. Sending goes through the Google MCP server's `send_email`, called only by the backend. If Google cannot be reached, the draft is kept as *Not sent* with **Try again**.

**Where it is in the app.**
- **Screening tab:** the final ranking shows each candidate's stage (Not shortlisted, then Rejected once their email is sent; Shortlisted, Interview scheduled, Interviewed, Hired, Rejected after interview) and email; an email chip opens the **Feedback emails** sub-tab (next to Final ranking and Requirement match), which lists everyone rejected at screening with why, **Write emails**, **Send all passed** and a review panel. A decision made on the Assessments tab shows here too. Shortlisting stays possible until the email is sent; then it is locked.
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
npm ci
npm run lint
npm run build
```

**Dependency versions** are pinned: every Python package in `backend/requirements*.txt` with `==`, and the exact frontend versions in `frontend/package-lock.json`. `npm ci` (also used by the frontend image) installs exactly the locked versions, so the `^` ranges in `package.json` never pull a newer one. Docker images are pinned to version tags in `docker-compose.yml`.

**Database viewer (optional):** pgAdmin runs only when asked for, so the normal start is unchanged:

```bash
docker compose --profile tools up -d pgadmin
```

Open http://localhost:5050 (only from this computer), sign in with `PGADMIN_EMAIL` and `PGADMIN_PASSWORD` from `.env`, then open **Servers › HireLucent** and enter `POSTGRES_PASSWORD`. The connection uses the default database user `hirelucent`; if `POSTGRES_USER` is changed, change it in `pgadmin/servers.json` too. Stop it with `docker compose stop pgadmin`. It shows real candidate data, so use it only on your own machine.

**Score stability check:** scores one already-screened candidate again 1–5 times, without saving, and compares the results with the saved scores. It prints IDs and numbers only:

```bash
docker compose exec backend python -m scripts.stability_check --candidate <id> --runs 3
```

### AI cost report

Every answer from the chat model (Gemini) adds one line to `logs/ai_usage.log`: the time, the API route and the graph step that asked, the job, candidate and interview IDs, and the input and output token counts Gemini reported. Prompts and answers are never written. The file is not rotated, so the whole history is kept. Embeddings, OCR, transcription and the face check run locally and cost nothing per call, so they are not counted.

The report turns the file into two CSV files in `logs/reports/`:

```bash
docker compose exec backend python -m scripts.ai_cost_report                                   # everything so far
docker compose exec backend python -m scripts.ai_cost_report --from 2026-10-27 --to 2026-10-27 # chosen days
docker compose exec backend python -m scripts.ai_cost_report --job 15                          # one job
```

- `ai_calls_<name>.csv`: one row per call, with its cost.
- `ai_cost_summary_<name>.csv`: totals by day, by route and by step (calls, retries, tokens, cost, share), the cost per CV screened, per candidate interviewed, per feedback email, per job and per hire (with the lowest and highest), and a monthly projection.

Costs use `AI_PRICE_INPUT_PER_1M` and `AI_PRICE_OUTPUT_PER_1M`; check them against the provider's pricing page. A call that gets no answer is not counted, as the provider does not bill it. Each call records its job when it is made, so deleting a candidate or an interview later does not change a job's cost, and the AI Agent chat that created a job counts for that job, including the messages before it was saved. Agent chat that never saves a job belongs to no job, so it appears only in the report without `--job`.

**Project layout:**

```
backend/
  app/
    api/routes/     REST and WebSocket endpoints
    services/       business logic (jobs, chat, intake, screening, shortlist, knowledge, tasks)
    graphs/         LangGraph workflows (recruiter/, screening/, qa_analysis/,
                    final_assessment/, feedback/, interview_quality/)
    ai/             AI model access: rate limit, retries, timeouts
    rag/            ChromaDB access, chunking, MCP client
    mcp_servers/    the custom RAG and Google MCP servers
    models/ schemas/ core/ db/
  alembic/          database migrations
  scripts/          seed, Google sign-in, check scripts and the AI cost report
  tests/
frontend/src/       pages, components, hooks, lib
mcp-blogger/        container for the community Blogger MCP server
docs/               architecture and LangGraph diagrams
```

**Branches:** `main` (final release), `dev` (completed modules) and one branch per module, merged into `dev` by pull request.

## Interview performance scoring (F9)

After the interview, HireLucent gives an **interview performance score** (0–100), kept apart from the CV score, and shows what it is made of: six dimensions, each 0–100, each pointing to the answers or requirements it rests on. The overall score is unchanged in form: **0.4 × CV score + 0.6 × interview score**.

**Two new things judged per answer** ([LangGraph 3](docs/LangGraph_3_QA_Analysis_30221_Farhan.pdf), `judge_batch`). Next to relevance, accuracy, completeness and articulation, the AI judges **problem-solving** (breaking a problem down, reasoning about causes, weighing options) and **depth of experience** (the candidate's own real work: examples, their own part, results), but only when the answer shows them, each with a quote. Code checks that the quote is in the candidate's answer, like every other quote; an unproven one is asked for again (up to 3 tries), then left out. An answer that does not call for them, such as a definition, is simply left out of those two dimensions, never marked down. They never change the answer's own score, so requirement coverage and the CV claim check are unaffected.

**The six dimensions** ([LangGraph 4](docs/LangGraph_4_Final_Assessment_Farhan_30221.drawio.pdf), `score_dimensions`, rule-based, no AI call):

| Dimension | Worked out from |
|---|---|
| Technical competency | Accuracy and completeness of each technical answer; a technical question not answered counts as 0 |
| Communication | Articulation of each answered question; a question not answered is left out |
| Relevance of responses | Relevance of every question asked; a question not answered counts as 0 |
| Problem-solving approach | The answers that showed problem-solving |
| Depth of experience | The answers that described the candidate's own work |
| Alignment with job requirements | Requirement coverage of the explored requirements, must-haves counting double; requirements never explored stay as evidence gaps |

The **interview score** is the average of the assessed dimensions, each counting equally. A dimension with nothing to judge (for example no technical question was asked) is **not assessed**: left out of the average, never scored 0, so a candidate is not marked down for a question nobody asked. At least **3** dimensions are needed for an interview score; with fewer, there is not enough interview evidence and no interview or overall score.

**Fairness.** Only job-related performance counts. Communication is about clarity and structure, never accent, fluency or speech-to-text spelling; the prompt says so. Scores are decision support only: the interviewer reads them (they cannot be edited) and decides.

**Where it shows.** The assessment page's **Interview performance** tab, right after Report (six bars; each opens to its answers, quotes and times, or its requirements; the tab's badge is the interview score), a link to it from the Report tab's score box, the two new criteria on the Q&A tab, small bars in the opened row of the Assessments list, six rows on the Compare page, and section *D · Interview performance* of the report PDF. Never in a feedback email.

**Interviews evaluated before F9** keep their interview score as the plain average of the answers and show *Breakdown not available*; **Evaluate again** gives them the six dimensions (the report goes back to draft).

**API.** `GET /interviews/{id}/assessment` and the ranked list (`GET /jobs/{id}/assessments`) return `interview_dimensions` (status, score, assessed, total, min_assessed and the six dimensions with their answers or requirements); each answer evaluation has `problem_solving` and `depth`. Migration `0018` adds `assessments.interview_dimensions`. The log event `interview_dimensions_scored` holds the session id, status and number assessed only.

## Interview quality assessment (F10)

F10 looks at **how the interview itself was run**, not at the candidate: whether the interviewer's questions gave useful answers, whether they explored the job's requirements, and how the speaking time was shared. It then recommends what to do differently next time, and compares how consistently the job's candidates were interviewed. It never changes a score of the candidate, the report, its approval or the decision, and it is never shown to the candidate or put in a feedback email.

**How it is worked out** ([LangGraph 6](docs/LangGraph_6_Interview_Quality_30221_Farhan.pdf), `backend/app/graphs/interview_quality/`). Everything is measured by code from data the evaluation already has (the Q&A pairs, the requirement coverage and the transcript's times); the AI only writes the recommendations.

| Part (0–100) | Worked out from |
|---|---|
| Questions | The share of job-related questions that gave a useful answer. A question gives little signal when it was not answered, the answer was very short (under 5 words) or off the question (relevance below 40); a technical or behavioural question linked to no requirement is not useful either. Small talk is left out |
| Coverage | Covered 1, weak ½, not explored 0 for each requirement, must-haves counting double |
| Interaction | 100 minus points: candidate speaking under 60% of the time (2 per point below, at most 40), small talk over 20% (1 per point over, at most 20), an interviewer stretch over 2 minutes (10 per extra minute, at most 20), an interview under half its planned length (20). A candidate speaking a lot is never marked down |

The **quality score** is the average of the three parts; **Good** from 70, **Needs improvement** from 50, otherwise **Poor**. Speaking time comes from the separate audio channels, so it is measured, not guessed.

**Recommendations.** Code writes every finding as a plain fact with what it rests on (for example *R5 Kubernetes (must-have) was never explored by any question*, *Q6 at 16:05 gave little signal: 3-word answer*). The AI turns them into up to 5 short, actionable recommendations, with an example question for a requirement that was not explored. It gets the job title, the findings and the interviewer's question texts with contacts masked, never the candidate's name or answers. Code then checks that every finding id exists and that every question id, requirement id and number in the text is in the findings it names; an unproven recommendation is asked for again (up to 3 tries), then left out. The evidence chips come from the findings, never from the AI. If the AI is not available, everything code measured is still saved and the tab offers **Check again**.

**Consistency across candidates** is worked out by code when it is read, from the job's checked interviews, so it is never out of date. The typical interview is the middle value of the length, the number of job-related questions and the candidate's share. An interview is flagged when a must-have it did not explore was explored in most of the other interviews, its length or number of questions is under half or over 1.5 times the typical one, or the candidate's share differs by more than 20 points. A requirement explored in fewer than half of the interviews is marked *Mostly missed*. It is shown from 2 checked interviews.

**Where it shows.** The assessment page's **Interview quality** tab, once there is a report (badge = the quality score): the score with its three parts and the questions and requirements behind them (each opens the Q&A analysis or Requirement coverage tab), the recommendations with their evidence, the speaking time (bar, longest stretch, small talk, follow-ups, length and a two-lane timeline) and this interview against the job's other interviews. The job's **Assessments** tab has a second view, **Interview consistency**, next to **Ranked candidates** (which still opens first). The evaluation's progress shows the new last step *Checking interview quality*.

**Interviews evaluated before F10** show *Interview quality not checked yet* with **Check interview quality**, which runs only this check (the report, its approval and the decision stay as they are). **Evaluate again** also checks it.

**API.** `GET /interviews/{id}/assessment` returns `interview_quality` (status, score, label, the three parts, the measurements, the findings and the recommendations with their evidence). `POST /interviews/{id}/assessment/quality` runs the check alone as a background task (its result is marked `quality_only`). `GET /jobs/{id}/interview-consistency` returns the job's comparison. Migration `0019` adds `assessments.interview_quality`. Log events (ids, counts, scores and labels only, never transcript or question text): `interview_quality_checked`, `interview_quality_recommendations_invalid`, `interview_quality_recommendations_dropped`, `interview_quality_failed`, `interview_quality_error`.

## Known limitations

- **Identity check (F7):** there is no liveness check yet, so a clear printed photo held up to the camera could pass; the interviewer still sees the live video and the label is advice only. Twins and close look-alikes can match each other. An old or poor application photo gives a lower score (the label then asks the interviewer to compare). Interviews scheduled before F7 have no PIN and no check. The photo inside a CV is not used.

- **CV claim check (F8):** the AI may judge a claim imperfectly (for example unverified where a person would say consistent); every result shows its evidence and the interviewer decides. A claim mentioned only in an answer whose question was lost from the transcript is not compared.

- **Interview scoring (F9):** the dimensions overlap a little (technical competency, communication and relevance all come from the same answer judgements, each looking at a different aspect). The AI decides whether an answer shows problem-solving or real experience, and may judge it imperfectly; every score shows the answers behind it. Interviews evaluated before F9 keep the plain answer average until evaluated again, so one job's ranking can mix both until then. An answer whose question was lost from the transcript counts towards no dimension.

- **Interview quality (F10):** a question that was lost from the transcript (and its answer) is not reviewed, so the interview can look as if it had fewer questions. Whether a question is linked to a requirement comes from the AI's segmentation, which may be imperfect; the Q&A analysis tab shows it. Speaking time counts what speech-to-text heard, so long silences are not counted. A poor-quality interview is flagged with its findings but does not suggest a new interview. Consistency compares only interviews with a quality check, so a job's interviews evaluated before F10 are left out until checked.

- **Score repeatability:** the model in use (Gemini 3.5 Flash-Lite) ignores the temperature setting, so scoring the same CV again can differ slightly. Measured on one candidate over 3 runs: requirement results, match and ATS scores were identical; the largest final-score difference was 2 points.
- **Screening speed:** measured on 27 Oct 2026, screening 5 CVs (parse, screen, score and rank) took 92 seconds, about 18 seconds per CV; a single CV took 33–56 seconds, because part of the time is a fixed start-up cost per run. The speed is limited by the free-tier LLM rate (15 requests per minute by default; about 3 calls per CV). Each run's start and end times are stored in the `tasks` table.
- **Google sign-in** expires after about 7 days while the consent screen is in Testing mode.
- **New applications count:** the "waiting" number compares the form's total responses with those already seen, so it can be wrong after responses are deleted from the form.
- **CV intake** is through Google Forms only; email intake is not built.
- **English only**, for CVs and interviews.
- On phones, the sidebar takes a lot of space at the top of the screen.
