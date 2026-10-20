# HireLucent: Project Context

> **Status labels:** **BUILT** = implemented, tested and pushed · **FINAL** = agreed, do not change unless the owner asks · **PROPOSED** = suggested design, confirm before major work · **PENDING** = owner decides later · **Not specified** = no information yet.
> Anything not marked **BUILT** is not in the code yet. For BUILT parts, the names in this file are the names used in the code. If the code and this file ever differ, **the code wins**; tell the owner which lines of this file to correct.
> **Last updated:** 20 Oct 2026, **Module 6 complete and merged into `dev`** (PR #5). Next: **Module 8 Stretch 1 (F7, Candidate Identification)** on `module/8-stretch-1-candidate-identification`, before Module 7 (owner's decision). Plan in §5.6 (PROPOSED).

---

## 1. Project overview

**HireLucent** is an AI-powered recruitment and interview platform (BJIT Academy AI Trainee final project, solo work by Shahriar Farhan, **due 27 Oct 2026**). It covers hiring end to end:
JD creation → job posting → CV collection → screening and ranking → scheduling → live video interview with transcription → assessment → ranked list → human decision.

**Core principle:** AI assists, people decide. Every score or flag must be traceable to CV or transcript evidence, and human-in-the-loop (HITL) approval gates all external or consequential actions.

### 1.1 Mandatory stack and rules
- Python 3.10+ (container uses 3.11), **FastAPI + Pydantic** (OpenAPI docs), **LangGraph** (real multi-node stateful graphs with retries and checkpointing), **Docker Compose** (single-command startup `docker compose up -d --build`, named volumes, `.env.example`, clean-machine reproducible), GitHub (incremental commits).
- **Repo branching (FINAL):** `main` + `dev` + one branch per module (`module/2-foundation-setup`, `module/3-pre-interview-core`, `module/4-video-interview`, `module/5-transcription`, `module/6-assessment`, …). A module branch is merged into `dev` by pull request when the module is complete; the next module branch is created from `dev`. `main` is merged **once**, after `dev` is fully complete.
- Local execution only. Only two roles: **Interviewer** (full access) and **Candidate** (interview only, no account).
- **Database migrations:** Alembic (FINAL), migrations `0001`–`0014` so far (`0014` adds `assessments.question_suggestions`; the next one is `0015`).
- **Code style (FINAL):** simple and easy to explain, never at the cost of requirements, quality or industry standards. Small, frequent commits in the format `<type>(<scope>): <Summary>`.

### 1.2 Scope
- **Core features (mandatory):**
  - **F1** CV screening and semantic ranking with met / partly met / not met evidence; candidates failing any must-have are excluded. **BUILT** (Module 3).
  - **F2** 0–100 scoring with per-dimension breakdown and justification. **BUILT** (Module 3).
  - **F3** 1-on-1 browser video interview with full lifecycle, controls and auto-reconnect. **BUILT** (Module 4).
  - **F4** live transcription, speaker-attributed through separate audio channels, with timestamps, saved incrementally. **BUILT** (Module 5).
  - **F5** Q&A analysis: segmentation, per-answer evaluation with evidence, reference-checked accuracy, requirement coverage. **BUILT** (Module 6).
  - **F6** consolidated assessment: scores and label, traceable report with human review, ranked list, PDF export, side-by-side comparison. **BUILT** (Module 6).
- **Client changes (override the BID):** the chatbot posts JDs to a portal with an API → **Blogger careers page** (BUILT); CVs arrive via **Google Form only for now** (BUILT; Gmail intake only if necessary, FINAL); future-dated interview scheduling is required (BUILT).
- **Stretch (only after all core features work):** F7–F10. Core F1–F6 are complete. **F7 is being built first** as Module 8 Stretch 1, one branch per stretch feature (`module/8-stretch-<n>-<feature>`), before the Module 7 innovation feature (owner's decision, 20 Oct). ⚠️ Clarification #21 says face or voice recognition is "not required in this phase"; the owner chose to go beyond it with face verification (Option B), which the BID's F7 and bonus rule (+3, N17) allow. Confirming with the trainer is suggested.
- **Innovation (exactly one):** Candidate Feedback Composer (initial choice, §4.8).
- **Out of scope:** cloud deployment/CI-CD, SSO, ATS/HRIS, offers/onboarding, multi-tenancy, mobile, model training.

### 1.3 Key constraints
- **Performance:** 20 CVs screened in about 5 minutes (state the measured time in README). **Not measured yet** (deferred). Screening runs at most 4 CVs at a time. AI pacing: 14 requests/minute overall, background screening capped at 10/minute, so the interviewer's chat stays responsive. One live interview plus background processing at the same time (checked in 4.10).
- **Security:** secrets only in `.env` (never committed, never pasted in chat); validate inputs, file types and sizes (PDF/DOCX, 10 MB); candidates can never reach scores, rankings, reports or the transcript (403 / interviewer-only data); no stack traces or prompts in error responses.
- **Privacy:** sample or synthetic CVs only; no personal data in the repo or logs; **raw audio/video never stored**; transcript text never logged; transcript text sent to Gemini for evaluation has contacts masked; report PDF file names carry no candidate name; Deepgram is asked not to keep audio for model training (`mip_opt_out=true`); AssemblyAI (optional second provider) cannot opt out of model training on the free plan, so it is used with test interviews only; candidate emails, phones and links never reach the LLM (masked in every prompt; the agent sees IDs and names only); README lists third-party services that receive candidate data (Gemini: CV text with contacts masked; Deepgram or AssemblyAI: interview audio; Google: name/email for the calendar invitation); candidate deletion endpoint; English only.
- **Persistence:** data survives restarts; LangGraph state is checkpointed and resumes after a restart. Tasks interrupted by a restart are marked failed at startup and can be started again. Transcript turns are saved one by one during the interview.

---

## 2. End-to-end workflow

### Setup: Knowledge Base page (BUILT)
- Upload documents with a **type**: `jd_template` → `jd_references`, `reference` → `rag_documents`, `questions` → `question_bank`. Question bank files have a **Roles** box: a role matches when it is part of the job title; empty = general (used by the room chat).
- `POST /knowledge/documents` → KnowledgeService (background): validate → extract → chunk → embed → store. `documents` row tracks status; delete removes the vectors.

### Stage 1: Create and publish the job (BUILT)

**Step 1: Interviewer signs in.** `POST /auth/login` (Argon2 hash, PyJWT HS256 token, 60 min, `sessionStorage`). First interviewer is seeded from `SEED_INTERVIEWER_*`.

**Step 2: AI-powered JD creation.** The **AI Agent** chat (`WS /chat`, streamed, one conversation per job) → Recruiter Agent (§4.1) uses RAG MCP `search_jd_references` (style references, "Source" pill). JD format (FINAL): About the Role, Responsibilities, Requirements, Nice to Have (extras only when asked). HITL loop with versioned drafts and a direct **Edit** button. Requirements checklist (`min_experience_years` as a **whole number**, items R1… with category, priority `must_have`/`preferred`, keywords) and AI-proposed scoring weights (technical skills / experience / qualifications, total 100%) confirmed in a card → `SaveJob` (HITL) → `jobs` row with job code (`HL-…`). Live job brief beside the chat.
- **Editing after saving (FINAL):** Edit requirements and weights from the job brief (`PUT /jobs/{id}/profile`); saving resets the screening. **Locked once the job has interviews** (409 + Edit disabled with a reason) because interviewed candidates need their screening results.

**Step 3: The agent posts the job.** Asks for the Google Form link → backend checks it (readable, required questions, one form per job) → post preview card → `PublishJob` (HITL) → backend calls Blogger MCP `create_post` → `jobs.status = published`, links saved.

**Step 4: Candidates apply** through the job's Google Form (name, email, CV upload to Drive).

### Stage 2: Screen and shortlist (BUILT)

**Step 5: Fetch CVs** (Applications tab, `POST /jobs/{id}/intake`, background task, no LLM): Forms API → Drive download → `candidates` rows (status `applied`), skip duplicates and deleted applicants (`removed_applications`). "New applications waiting" count (count-based; known limitation).

**Step 6: Screen CVs** (Screening tab, `POST /jobs/{id}/screen`) → CV Screening graph (§4.1). Results: requirement matches with evidence, match ranking, dimension scores, ATS score, final score (0.8 × criteria + 0.2 × ATS), final ranking, summary, exclusion reasons, CV facts. Two sub-tabs (Requirement match / Final ranking), Show dropdown, search, expandable rows.
- **Human step (FINAL): no automatic shortlist.** Shortlist one by one, by top N or by minimum score; clear the shortlist. **The shortlist is the selection for interview (FINAL):** shortlisted candidates are scheduled directly; status `selected` stays unused.
- Candidate delete at any stage removes the candidate, CV file and vectors. Screening reset when requirements change (not allowed once interviews exist).

**Step 7: Schedule the interview (BUILT, Module 4)**
- **Two ways (FINAL):** (a) the **AI Agent** conversation: tools `GetCandidates` (read-only; lists ranked candidates with status and interview status), `ScheduleInterviews`, `RescheduleInterview`, `CancelInterview` (all three HITL cards with an email preview); (b) the job's **Interviews tab**: schedule form (candidates, date, time, length 30/45/60, break), reschedule and cancel with confirm dialogs.
- If a candidate is not shortlisted, the agent tells the interviewer to shortlist them on the Screening tab first (no shortlisting from the chat).
- **Email (FINAL):** the candidate gets **only Google Calendar's invitation** (created by the `mcp-google` server with `sendUpdates="all"`): invitation, updated invitation on reschedule, Google's cancellation notice. Title "HireLucent video interview – <job>". Description order: Hello → **editable message** → When → **Join link** → tips → signature "HireLucent Careers". The interviewer can edit the message paragraph on all cards and dialogs (or by typing in the chat); `POST /jobs/{id}/interviews/preview` shows the exact email with "[private link]".
- **Rules:** times stored in UTC; screens show the browser's local time; the agent reads typed times in `APP_TIMEZONE` (default Asia/Dhaka); minimum notice `INTERVIEW_MIN_NOTICE_MINUTES` (15; 1 while testing); no overlapping interviews for the same interviewer. Candidate status → `interview_scheduled`.
- Interviews tab lists Upcoming / Completed / Cancelled (pills); cancelled rows can be deleted from history. Candidates with an interview show "Interview scheduled" + See interview on the candidate lists. Deleting a job is blocked while it has upcoming interviews.

### Stage 3: Live interview (BUILT, Modules 4–5)

**Step 8: Candidate joins (no account)**
- Link `/interview/<token>`: `secrets.token_urlsafe(32)`, **only its SHA-256 hash is stored**; new link on reschedule, old link dead on reschedule/cancel.
- **Three tokens:** (1) the join link token (proves the invitation); (2) the **candidate pass**, a JWT from `core/security.create_access_token` with role, session_id and link fingerprint, checked by `api/deps.require_candidate`; (3) the **LiveKit room token** for room `interview-<id>`, checked by the LiveKit server.
- Pages: pre-join (job, local time, camera/mic test, **consent**) → **waiting room** (heartbeat every few seconds; "Candidate waiting" on the Interviews tab, gone ~15 s after leaving) → room after **Admit**. Join opens `JOIN_OPENS_MINUTES_BEFORE` (10; 60 while testing) before the start. After end/cancel: "interview has ended" page.
- Endpoints: `POST /join/info`, `/join/enter`, `GET /join/status`, `POST /join/leave`, `/join/room`.

**Step 9: Video interview with live transcription**
- **Video (FINAL):** self-hosted **LiveKit** (`livekit` container, ports 7880/7881/7882 udp), `livekit-client` in the browser. Interviewer room (v7): left = candidate info / Suggested questions tabs; middle = one big 16:9 video (own video as a small floating tile, swap by click) with small in-video controls, and the **Live transcript** panel below; right = **AI Agent** (read-only room chat) / **Message** (live text messages with the candidate, not stored) tabs. Candidate room: video with labelled buttons below and a Message panel (closed by default). Full screen, screen share, auto-reconnect (keeps trying while the interview runs; "Still trying" card after 30 s). The interview never ends by itself (timer turns amber after the planned end); only the interviewer ends it; the candidate's Leave keeps it running.
- **Suggested questions (BUILT):** generated only on click (5 per click, "More questions"), from the candidate's CV and screening data; mark as asked.
- **Room AI chat (FINAL, BUILT):** thread `interview-<session id>`, Recruiter Agent in **interview mode** (read-only tools only: JD, requirements, this candidate, `search_question_bank` filtered by role); external actions refused in code.
- **Transcription (BUILT, Module 5):**
  - `transcription-worker` container checks the database every few seconds for in-progress interviews and joins each room as a **hidden** participant (no audio/video publishing; may send data). It receives the interviewer's and the candidate's microphones as **two separate streams**, so the speaker label comes from the channel (no diarisation).
  - **Two switchable providers (FINAL):** `STT_PROVIDER=deepgram` (default) or `assemblyai` (or `off`); switch by editing `.env` and running `docker compose up -d --force-recreate transcription-worker` (a running interview is rejoined within seconds). `capture.open_sink()` picks the sink from `capture.SINKS`.
  - Shared code in `app/workers/stt_stream.py` (`StreamingSink`): 30 s audio queue while disconnected, reconnect with waits 1 → 2 → 4 → 5 s (max 5 s, `next_wait`), unreadable or error messages skipped and logged by kind only, close codes logged as numbers, delay measured (`DelayMeter`), turns saved and pushed. Each provider file only says how to connect and read replies.
  - **Deepgram** (`deepgram.py`): `nova-3`, English, interim results, smart format, endpointing 300 ms, utterance end 1000 ms, `mip_opt_out=true`, keep-alive during silence, optional job **keyterms**. Final pieces are joined into a **turn** at each pause (or after 30 s) by `TurnBuilder`.
  - **AssemblyAI** (`assemblyai.py`): Universal Streaming v3, `universal-streaming-english`, global address `wss://streaming.assemblyai.com/v3/ws` (its EU data zone accepted the connection but returned no text in testing), `format_turns=true`, job keywords as `keyterms_prompt`, `Terminate` at the end, queued audio sent at most 1.5× real time after a drop. `AssemblyTurnBuilder` shows every heard word live (sure or not) and saves the formatted turn.
  - Turns are **saved immediately** to `transcript_turns` (speaker, `start_ms`, `end_ms` from the interview start, text). An audio clock corrects times after muted gaps. Overlapping speech = separate entries per speaker.
  - **Measured delay (reported, AssemblyAI, 17 Oct):** saved lines arrive 0.08–0.09 s on average after the speaker stops, under 0.9 s in the slowest 5%; live words appear as they are spoken (target < 2 s, clarification #8). Logged per stream in `stt_stream_finished` (`live_/final_delay_avg/p95/max_ms`).
  - **Live push (FINAL: option A):** the worker sends `live` (words still being spoken), `turn` (each saved turn with its id) and `status` (`listening` / `paused` / `off`, every 5 s) over LiveKit data, **to the interviewer only**. LiveKit blanks the sender identity for hidden participants, so the browser accepts transcript data only from a sender with **no identity** (the candidate cannot fake lines).
  - **Live transcript panel (FINAL):** newest line at the bottom, auto-scroll that pauses when scrolling up + "N new · Jump to latest"; **one row per turn** (not grouped) with avatar ("You" / candidate initials), name ("You" / candidate's first name), time from the start (clock time on hover); grey interim words with "●●● speaking"; states Not started / Loading / Listening / Paused (banner "Transcription paused, reconnecting…") / Not available (no status for 15 s or speech-to-text off). Saved turns load first and after every reconnect.
  - Settings: `STT_PROVIDER` (`deepgram` | `assemblyai` | `off`), `DEEPGRAM_API_KEY`, `ASSEMBLYAI_API_KEY`, `ASSEMBLYAI_URL`, `ASSEMBLYAI_MODEL`, `STT_KEYTERMS` (`true` | `false`).
  - `GET /interviews/{id}/transcript` (interviewer only): ordered turns with `start_ms`, `end_ms`, `spoken_at` (clock time), text.
  - **Transcript viewer (FINAL, BUILT, 5.6):** full page `/app/interviews/:sessionId/transcript` inside the app layout, opened from **View transcript** on Completed rows of the Interviews tab; read-only, interviewer only; no new endpoint (uses `GET /interviews/{id}` + `GET /interviews/{id}/transcript`). Search ignores case and matches inside words; all matches highlighted, current one outlined; "3 of 12", ↑/↓, Enter / Shift+Enter, Esc clears; "Nobody said …" when nothing matches. Timeline with two speaker lanes, match ticks, a box for the part on screen; clicks, minute markers and ticks jump the list. Text only, **no audio playback**. **Download .txt** built in the browser: header + `[hh:mm:ss] Speaker: text`; file name `transcript_<job code>_<date>.txt` (no candidate name); disabled when there are no turns ("No transcript for this interview"). Files: `pages/TranscriptPage.jsx`, `components/transcript/TranscriptTimeline.jsx`, `TranscriptTurns.jsx`, `lib/transcript.js`.

**Step 10: Interview ends.** `POST /interviews/{id}/end` → room closed → worker saves the last words → status `completed`, `ended_at` set → candidate link and passes stop working.

### Stage 4: Assess and decide (BUILT, Module 6: F5, F6; decision PENDING)

**Step 11: Evaluate the interview (BUILT).** On the job's **Interviews** tab, completed rows show **Evaluate** and the tab shows **Evaluate all (N new)**. One evaluation runs at a time as a background task with progress ("Finding the questions and answers → Judging answers and checking references → Writing the report"); one interview failing does not stop the others. `EvaluationService` runs **LangGraph 3 (Q&A Analysis)**, then **LangGraph 4 (Final Assessment)** (§4.1). An interview analysed before reports existed shows **Write report** (LangGraph 4 only). Once an interview has a report, the screens no longer offer Evaluate (the API still allows re-evaluation; a Re-evaluate option was offered and is PENDING).

**Step 12: Review the report (BUILT, HITL).** Assessment page `/app/interviews/:sessionId/assessment` with tabs **Q&A** (each question with its answer, four criteria, justification, evidence quote and accuracy source; small talk marked, follow-ups indented), **Coverage** (requirement by requirement with CV status; suggested questions to add to the bank) and **Report** (scores and label, summary, strengths and weaknesses with source chips, evidence gaps, areas to verify). The report is a **draft** until the interviewer **approves** it (confirm dialog), **requests changes** (note required, AI rewrites) or **edits** it (new summary and/or remove points; nothing can be added). Approval records who and when and marks the candidate `assessed`. **Approve all drafts** on the Assessments tab approves every waiting draft (confirm dialog).

**Step 13: Ranked list, report export and comparison (BUILT).** Job tab **Assessments**: count boxes (Strong fit, Possible fit, Not a fit, Waiting for your review), filters, ranked rows (overall score desc, then interview score, then name; drafts marked) with an arrow to show the score parts and coverage; unranked rows (no overall score) below, latest first, with the reason. **Print** and **Download PDF** on the Report tab. Tick up to **3** ranked candidates → **Compare** page `/app/jobs/:jobId/compare?ids=…` (scores and requirements side by side, best value highlighted, no highlight when all are equal). Job tabs Interviews and Assessments get a green tick when their step is finished (§3.5).

**Step 14: Decision:** Hire / Hold / Reject (`PATCH /candidates/{id}`, columns exist, endpoint not built; timing PENDING). Candidate Feedback Composer starts here.

---

## 3. Technical architecture

### 3.1 Components

| Component | Technology | Status |
|---|---|---|
| Frontend | React 19 + Tailwind CSS v4 + Vite, React Router, lucide-react, react-markdown, `livekit-client`; fonts Plus Jakarta Sans and Figtree; ESLint (react-hooks v7); code formatted Prettier-style (no semicolons, single quotes, width 100) | BUILT |
| Backend | FastAPI + Pydantic v2, SQLAlchemy 2, Alembic | BUILT |
| Services | auth, chat (+ conversation store/view), knowledge, job, job_post, job_deletion, intake (google_forms, google_drive, google_client), screening, shortlist, task, blogger, text_extraction, session, scheduling, interview_emails, interview_times, interview_context, join, room, video, question, interview_chat, transcript, **evaluation_service, report_pdf** | BUILT |
| AI workflows | LangGraph + PostgresSaver | Recruiter Agent, CV Screening, **Q&A Analysis, Final Assessment** BUILT |
| MCP clients | `app/mcp_clients/registry.py` (`mcp_servers()`: rag offered to the agent; google and blogger backend-only with `allowed_tools`) + `app/mcp_clients/client.py` (`call_tool`, `agent_tool_definitions`, `call_agent_tool`) | BUILT |
| MCP servers | **mcp-rag** (custom, port 8001: `search_jd_references`, `search_question_bank`, `verify_answer`), **mcp-blogger** (zachsladecode/blogger-mcp-server, pinned, supergateway, port 8002: `create_post`), **mcp-google** (custom, port 8003: `send_email`, `create_calendar_event`, `update_calendar_event`, `cancel_calendar_event`) | BUILT |
| Relational DB | PostgreSQL 16 | BUILT |
| Vector DB | ChromaDB 1.5 (cosine) | BUILT |
| Embeddings | `qwen3-embedding:0.6b` via Ollama (temporary; OpenAI selectable) | BUILT |
| LLM | Gemini 3.5 Flash-Lite free tier (OpenAI selectable); pacing 14/min, background 10/min; retries; room chat has shorter timeouts (`ROOM_AI_*`) | BUILT |
| Video | Self-hosted LiveKit (`livekit/livekit-server:v1.13.7`) | BUILT |
| Speech-to-text | **Deepgram nova-3** (default) or **AssemblyAI Universal Streaming**, switchable with `STT_PROVIDER` | BUILT |
| Google APIs | One Cloud project: Forms, Drive (direct), Blogger (MCP), Calendar + Gmail send (mcp-google) | BUILT |
| CV parsing / OCR | PyMuPDF, python-docx, Tesseract | BUILT |
| Report PDF | PyMuPDF `Story` + `DocumentWriter` (`services/report_pdf.py`) | BUILT |

### 3.2 Docker Compose services (BUILT)
`postgres`, `backend`, `frontend` (nginx), `mcp-rag`, `mcp-google`, `mcp-blogger`, `livekit`, `transcription-worker` (shares the livekit network: `network_mode: service:livekit`), `chromadb`, `ollama` + `ollama-pull`. One `docker-compose.yml`. `./secrets` (git-ignored) holds the Google files; `./logs` bind mount.
- **Optional `pgadmin`** (`dpage/pgadmin4:9.8`, **`tools` profile**, so the single-command startup is unchanged): bound to `127.0.0.1:5050` only; the HireLucent server is pre-set by `pgadmin/servers.json`; sign-in from `PGADMIN_EMAIL` / `PGADMIN_PASSWORD` in `.env`; start with `docker compose --profile tools up -d pgadmin`. The database password is `POSTGRES_PASSWORD`.

### 3.3 Authentication and roles
| Token | Holder | Scope |
|---|---|---|
| App JWT | Interviewer | All interviewer APIs, 60 min |
| Join link token | Candidate | Only its SHA-256 hash stored; finds the interview |
| Candidate pass (JWT) | Candidate | One interview (role, session_id, link fingerprint) |
| LiveKit token | Interviewer, candidate, worker | One room `interview-<id>`; worker's is hidden, no audio/video publishing |

### 3.4 Data stores
**PostgreSQL tables (BUILT):** `users`, `jobs`, `candidates`, `screening_results`, `removed_applications`, `conversations`, `documents`, `tasks`, `interview_sessions` (times, join token hash, calendar event id, status `scheduled`/`in_progress`/`completed`/`cancelled`, joined/started/ended/consent/cancelled times, `candidate_seen_at`, `suggested_questions` JSONB, `created_by`), `transcript_turns` (session_id, speaker `interviewer`/`candidate`, start_ms, end_ms, text), `assessments` (one row per interview: status `analysed` → `draft` → `approved`; `qa_evaluations`, `coverage_map`, `question_suggestions` from LangGraph 3; `cv_score`, `interview_score`, `overall_score`, summary, strengths, weaknesses, gaps, `areas_to_verify` from LangGraph 4; `approved_by`, `approved_at`; the label `suitability` is computed from `overall_score`, not stored), LangGraph checkpoint tables.
**Candidate statuses:** `applied`, `screening_failed`, `excluded`, `screened`, `shortlisted`, `selected` (unused), `interview_scheduled`, `assessed`.
**Never stored:** raw audio/video, live messages, join tokens (only hashes), JWTs, LiveKit tokens.

### 3.5 UI design
> - The owner wants a **very professional, modern and beautiful UI**.
> - **Before implementing any UI screen or change: share the understanding, show a mockup on the design canvas, wait for approval, then apply it exactly.**
> - Design canvas: https://claude.ai/artifact/1YsLaBugibMF1nbsWtcWYj (all approved mockups; Module 5 boards: `M5LiveTranscript`, `M5TranscriptStates`, `M5TranscriptViewer`, `M5TranscriptViewerStates`; Module 6 boards: `M6Assessments`, `M6AssessmentsStates`, `M6Report`, `M6ReportStates`, `M6PdfA`, `M6PdfB`, `M6CompareSelect`, `M6Compare`).

Theme (FINAL): clean corporate SaaS, white/pale-blue backgrounds, blue primary `#1557E0`, navy headings `#0B1F4B`, body text `#51607A`, rounded cards, subtle shadows; each stage its own colour (no dark navy fills). Tailwind tokens in `frontend/src/index.css` (brand, navy, body, mist, tint, line, success, warning, danger, teal, amber, violet + `-soft`).

**Screens (BUILT):** landing, login, sidebar (Dashboard, Jobs, AI Agent, Knowledge Base; stays in place while the page scrolls on wide screens), Dashboard, Jobs page, job page tabs (Job post, Applications, Screening, Interviews, **Assessments** with a "to review" badge), AI Agent page (cards, job brief), Knowledge Base, interviewer room `/app/interviews/:sessionId/room`, transcript viewer `/app/interviews/:sessionId/transcript`, **assessment page** `/app/interviews/:sessionId/assessment` (Q&A, Coverage, Report tabs), **compare page** `/app/jobs/:jobId/compare?ids=…`, candidate pages `/interview/:token` (pre-join, waiting, room, ended).
**Job tab ticks (BUILT):** each tab turns green when its step is finished; Interviews when at least one interview is completed and none is scheduled or in progress; Assessments when every completed interview has an approved report. The open tab is always blue.
**Next screens:** Module 7 (mockups first).

---

## 4. Implementation details

### 4.1 LangGraph workflows
**LangGraph 1: Recruiter Agent** (BUILT, `app/graphs/recruiter/`): nodes `load_context`, `agent`, `human_approval` (interrupt), `call_tools`, `handle_error`, `respond`. Tools: RAG MCP `search_jd_references` (read-only, via `call_agent_tool`), `SaveJob`, `PublishJob`, `GetCandidates` (read-only), `ScheduleInterviews`, `RescheduleInterview`, `CancelInterview` (HITL). PREPARERS build approved details from app data; invalid tool details go back to the model to fix. Threads: one per job conversation; `interview-<id>` for the read-only room chat (interview mode).
**LangGraph 2: CV Screening** (BUILT, `app/graphs/screening/`): per-CV branches (max 4), resume-from-step, `extract_text` → `run_ocr` → `parse_cv` → `check_must_haves` (FINAL option B) → `match_requirements` → `compute_ats_score` → `score_candidate` → `save_result`; `log_failure`; `rank_candidates` (never shortlists).
**LangGraph 3: Q&A Analysis** (BUILT, `app/graphs/qa_analysis/`): `load_transcript` → `segment_qa` (AI: pairs with kind `technical`/`behavioural`/`company`/`small_talk`, `follow_up_of`, requirement ids; checked by `build_pairs`; retry up to 3) → `classify_question` (rule: small talk skipped, unanswered questions score 0 without an AI call, the rest in **batches of 4**, one parallel branch each with `Send`) → `evaluate_answers` (per batch: `retrieve_references` through RAG MCP `verify_answer` for technical and company answers, up to 2 passages within distance 0.6 → `judge_batch`: AI scores relevance, accuracy, completeness, articulation 0–100, answered/partly/not, justification, evidence quote; checked in code; retry up to 3) → `collect_evaluations` → `map_coverage` (rule) → `suggest_questions` (rule + RAG MCP `search_question_bank`, ≥ 0.8 similar = already in the bank; nothing added until the interviewer picks) → `save_analysis` (status `analysed`); `handle_error`.
- Answer score = average of the criteria that apply (0 when not answered), worked out by code. Accuracy source: `reference` (passage kept), `ai_judgement` (technical, no usable reference) or `not_checked` (company with no reference, or accuracy left out).
- **Real-conversation robustness (6.11):** a not-answered question needs no accuracy or quote; quotes are matched across the answer's turns and at ≥ 0.85 similarity for 3+ words (`find_quote`), keeping the transcript's own words; a wrong turn number is corrected; after the last attempt the batch keeps what can be trusted (no unproven quote, a reference not given ignored, missing accuracy = not checked) and a question the AI skipped is asked once more alone; the Knowledge Base being down means judging without references. Only a question that is never judged fails the interview. Prompts tell the AI to judge meaning, not speech-to-text spelling, and how real conversations go (interviewer "mm-hmm", rephrased questions, hints, call problems).
- Coverage: covered (average ≥ 60), weak (< 60), not explored; **mixed** when covered but one answer < 40; CV status shown beside each requirement.
- Thread `evaluation-{task_id}-{session_id}`.

**LangGraph 4: Final Assessment** (BUILT, `app/graphs/final_assessment/`): `load_results` → `compute_scores` (rule: interview score = average of evaluated answers; **overall = 0.4 × CV + 0.6 × interview**, none if either part is missing; label **strong fit ≥ 70, possible fit ≥ 60, otherwise not a fit**; evidence gaps and areas to verify) → `synthesize_report` (AI: summary, up to 5 strengths and 5 weaknesses, each with transcript quotes and/or CV requirements) → `check_traceability` (code: quote in that answer with the same tolerance as LangGraph 3; a strength needs an answer ≥ 60 or CV met/partly met; a weakness needs an answer < 75 or CV unmet/partly met; retry up to 3, then untraced claims are dropped) → `save_draft` → `human_review` (`interrupt`) → **approve** → `save_assessment` → `update_candidate_status` (`assessed`); **request_changes** → `synthesize_report` with the note; **edit** → `apply_edits` → `save_draft`. AI down on a first draft → `handle_error`; during a rewrite → `revision_failed`, the old draft stays and the graph waits again. Thread `final-assessment-{session_id}`, deleted before each new report.
- **Findings (each fact once):** evidence gaps = requirements never explored, must-haves first, with the CV result on the same line; areas to verify = one line per asked question, for its main reason (not answered → poor answer behind a mixed requirement → accuracy not checked); "No job-related questions" when there were none. Claim ids S1/W1/G1/V1.
- Diagrams updated to the built graphs: `docs/LangGraph_3_QA_Analysis_30221_Farhan.pdf`, `docs/LangGraph_4_Final_Assessment_Farhan_30221.drawio.pdf` (draw.io sources kept by the owner).

### 4.2 RAG design (BUILT parts)
Collections: `jd_references`, `cv_embeddings`, `question_bank` (with roles), `rag_documents`. Collections are fixed in code, never chosen by the LLM. `QUESTION_BANK_MAX_DISTANCE`, `JD_REFERENCE_MAX_DISTANCE` and `REFERENCE_MAX_DISTANCE` (all 0.6). Only Knowledge Base documents of type `reference` are used to check answer accuracy (clarification #10).

### 4.3 Tools and MCP
| Tool | Type | HITL | Status |
|---|---|---|---|
| `search_jd_references`, `search_question_bank` | RAG MCP | No | BUILT |
| `verify_answer` | RAG MCP, called by LangGraph 3 | No | BUILT |
| `SaveJob`, `PublishJob` (→ Blogger `create_post`) | Backend | Yes | BUILT |
| `GetCandidates` | Backend, read-only | No | BUILT |
| `ScheduleInterviews`, `RescheduleInterview`, `CancelInterview` (→ mcp-google calendar tools) | Backend | Yes | BUILT |
| `send_email` (mcp-google) | Backend-only | Yes | Kept for later (innovation) |
External MCP tools are called only by the backend after approval and are never listed to the LLM.

### 4.4 Google integration
OAuth consent in Testing mode: **the sign-in expires about every 7 days** → run `python -m scripts.google_auth` in `backend/` on the host, then `docker compose restart mcp-blogger mcp-google`. **Next renewal due around 19 Oct 2026.** Scopes: blogger, forms (read), drive (read), gmail.send, calendar.events. Files in `secrets/` (never on GitHub; copied between PCs by USB). Check scripts: `form_check`, `blogger_check`, `mcp_check`, `google_check`.

### 4.5 API endpoints (BUILT; interviewer role unless marked)
- Public: `GET /health`, `POST /auth/login`. `GET /auth/me`, `GET /ai/status`.
- Chat: `WS /chat`, `GET/DELETE /chat/conversations…`, `GET /chat/{thread_id}`, `POST /chat/messages`, `POST /chat/{thread_id}/approval`, `PUT /chat/{thread_id}/description`.
- Knowledge: `POST/GET /knowledge/documents`, `DELETE /knowledge/documents/{id}`.
- Jobs: `GET /jobs`, `GET/DELETE /jobs/{id}`, `PUT /jobs/{id}/profile`, `POST /jobs/{id}/archive` (no UI), `GET /jobs/{id}/activity`, `POST /jobs/{id}/intake`, `GET /jobs/{id}/intake/status`, `GET /jobs/{id}/candidates`, `POST /jobs/{id}/screen`, `POST/DELETE /jobs/{id}/shortlist`.
- Candidates: `GET /candidates/{id}/cv`, `PUT /candidates/{id}/shortlist`, `DELETE /candidates/{id}`.
- Interviews: `GET/POST /jobs/{id}/interviews`, `POST /jobs/{id}/interviews/preview`, `GET /interviews/rules`, `GET /interviews/{id}`, `POST /interviews/{id}/room`, `/admit`, `/end`, `GET /interviews/{id}/transcript`, `GET/POST /interviews/{id}/questions`, `PATCH /interviews/{id}/questions/{qid}`, `GET/POST /interviews/{id}/chat`, `PUT /interviews/{id}` (reschedule), `POST /interviews/{id}/cancel`, `DELETE /interviews/{id}` (cancelled only).
- Candidate (pass): `POST /join/info`, `/join/enter`, `GET /join/status`, `POST /join/leave`, `/join/room`.
- Tasks: `GET /tasks/{id}`. **To remove later:** demo endpoints `/graphs/demo…`, `POST /tasks/demo`.
- Assessments (Module 6): `POST /interviews/{id}/evaluate`, `POST /jobs/{id}/evaluate`, `GET /jobs/{id}/evaluation`, `POST /interviews/{id}/report`, `GET /interviews/{id}/assessment`, `POST /interviews/{id}/assessment/questions`, `POST /interviews/{id}/assessment/review` (approve / request_changes / edit), `GET /interviews/{id}/assessment/report.pdf?tz=` (file `assessment_<job code>_<date>.pdf`), `GET /jobs/{id}/assessments` (ranked list with coverage, also used by the comparison), `POST /jobs/{id}/assessments/approve` (approve all drafts). All interviewer-only (candidates get 403).
- **Later:** decision (Hire/Hold/Reject), Re-evaluate in the UI (PENDING).

### 4.6 Error handling and logging
JSON logs (IDs and numbers only: no names, emails, CV text, transcript text, tokens, keys or prompts). Worker events (all with `provider`): `transcription_worker_started` (provider, key set), `interview_audio_joined`, `stt_connected`, `transcript_turn_saved` (speaker, times, word count), `stt_stream_finished` (turns, dropped chunks, skipped messages, delay figures), `stt_refused` (HTTP status), `stt_disconnected` (error type, close code), `stt_error_message`, `stt_message_skipped`, `stt_not_configured`. Evaluation events (ids, counts and labels only): `qa_segmentation_empty`, `qa_references_found`, `qa_references_unavailable`, `qa_evaluation_invalid` (attempt, problem labels such as `quote_not_found`, `accuracy_missing`), `qa_evaluation_kept`, `assessment_report_untraced`, `assessment_claims_dropped`, `assessment_reviewed`, `assessments_approved`, `report_written`, `report_pdf_built`, `evaluation_finished`. PENDING: simplify the logging code after all other tasks.

### 4.7 Innovation feature: Candidate Feedback Composer (initial choice, Module 7)
After Hold/Reject: draft respectful feedback from saved job-related evidence only, fairness check, HITL edit/approve, send via `send_email`. Graph, endpoint, UI and the 300–500 word rationale (owner's own reasoning) not yet specified.

---

## 5. Development status (19 Oct 2026)

### 5.1 Redmine tree and status
- **Module 2** Foundation: BUILT, merged into `dev`.
- **Module 3** (Story #647080, F1 + F2): BUILT, merged into `dev`.
- **Module 4** (Story #648326, F3): BUILT, merged into `dev` (14 Oct).
- **Module 5** (Story #648345, F4): BUILT, merged into `dev`.
  - Features 22–27 complete (#648346, #648347, #648349, #648354, #648355, #648357); AssemblyAI provider `Refs #648360`.
- **Module 6** (F5 + F6), branch `module/6-assessment`: **all tasks done, full test passed**; next: PR into `dev`. Story and feature ids: (fill in from the Redmine tree).
  - Q&A segmentation #650073 (+ #650074 multi-part and small talk) · Response evaluation #650075 · reference-based accuracy #650076 · justification with evidence #650077 · requirement coverage #650078 · Q&A screens #650079 · consolidated assessment #650080 (scores and label) and #650081 (strengths, weaknesses, gaps, areas, traceability) · report view #650082 · export and print #650083 · candidate comparison #650084 (also ranked list and Assessments tab).
  - pgAdmin (extra tool): `Refs #646551`. Fixes from the full test: `Refs #650075, #650076, #650080, #650081, #650084`.

### 5.2 Module 6 step log
| Step | Content | Commits | Status |
|---|---|---|---|
| 6.1 | LangGraph 3 segmentation (pairs, kinds, follow-ups, multi-part, small talk); README note on transcript text sent to Gemini (#650073) | `c392cc1`, `ddeb296`, `30f7989` | ✅ |
| 6.2 | Answer evaluation in batches with evidence and justification (#650075, #650077) | `b043ce4`, `a757b4f`, `cef1b04` | ✅ |
| 6.3 | RAG MCP `verify_answer`; accuracy checked against references (#650076) | `1397560`, `e2a7aa8`, `64faf7c` | ✅ |
| 6.4 | Requirement coverage; question bank suggestions; migration `0014` (#650078) | `4e4090a`, `b864d12`, `055290d` | ✅ |
| 6.5 | Evaluation runs per job, Evaluate / Evaluate all, sticky sidebar, assessment page (Q&A, Coverage) (#650079) | `ce98960`, `9a4d78b`, `3cbfa11`, `e7f3bea` | ✅ |
| 6.6 | LangGraph 4: scores, label, report, traceability, HITL review (#650080, #650081) | `78eaf3f`, `8e32571`, `22057a9` | ✅ |
| 6.7 | Ranked list API and Assessments tab, Write report (#650084) | `4af6a77`, `8c40b5b` | ✅ |
| 6.8 | Approve all drafts, approver shown, Report tab (#650082) | `194f15d`, `aaa5598` | ✅ |
| 6.9 | Report PDF, Print and Download (#650083) | `bab4a90`, `92056bd` | ✅ |
| 6.10 | Coverage in the ranked list; compare up to 3 candidates (#650084) | `061dd58`, `63115d9` | ✅ |
| Extra | Optional pgAdmin viewer (tools profile) (`Refs #646551`) | `cc7f20e` | ✅ |
| 6.11 | Full test by the owner; fixes: messy transcripts, report quote tracing, each finding once, job tab ticks | `dcaca5b`, `bb802df`, `d93374b`, `0bee242` | ✅ |
| End | Redmine descriptions, docs update, PR into `dev` | — | PR next |

### 5.3 Module 6 decisions (16–19 Oct)
- Evaluation runs on request (Evaluate / Evaluate all), never automatically; one at a time, in the background with progress.
- Reference material for accuracy = Knowledge Base documents of type `reference`; without one, technical accuracy is the AI's own judgement and company accuracy is not checked (never guessed).
- Overall score 0.4 × CV + 0.6 × interview; label thresholds 70 / 60; the label is decision support only.
- HITL report review: approve / request changes (note) / edit (summary and remove points only); plus **Approve all drafts** with a confirm.
- Question bank: suggestions only; the interviewer picks what is added.
- Export: generated PDF (PyMuPDF) plus Print; the file name has no candidate name.
- Comparison: up to 3 ranked candidates, scores and requirements side by side, best value highlighted.
- Evaluation must not fail on real conversations: keep what can be trusted instead of failing (6.11).
- Findings appear once: unexplored requirements only as evidence gaps; areas to verify are about asked questions, worded "to double-check before deciding".
- pgAdmin is optional (tools profile), localhost only, so the single-command startup is unchanged.
- Way 2 (two devices on the same Wi-Fi): handled manually with Cloudflare quick tunnels (step-by-step guide given; no code change); ngrok kept as a backup.

### 5.6 Module 8 Stretch 1: F7 Candidate Identification (PROPOSED, plan agreed 20 Oct)
Branch `module/8-stretch-1-candidate-identification` (from `dev`). WBS: Module 8, Day 18. Nothing is built yet; the details below are the agreed plan.
- **Enrolment (keeps the FINAL "Google Form only" decision):** the job's Google Form gets a **recent passport-size photo** upload (JPG/PNG, face clearly visible) and a **biometric consent** checkbox. At **Fetch CVs** the backend checks the photo (type, size, exactly one face, big and sharp enough), makes a **face code** (embedding) and **deletes the photo**. Statuses: face enrolled / photo not usable / no photo / no consent. A live photo at application would need an own Apply page (changes a FINAL decision): not chosen.
- **Interview PIN (PROPOSED):** an **8-digit PIN** created at scheduling, placed in the **calendar invitation right under the join link** ("Interview PIN: 4829 1067", keeps the FINAL "calendar invitation only" decision). Pre-join asks for the PIN first; 5 wrong tries lock the link for 15 minutes; only an **Argon2 hash** is stored; new PIN on reschedule, dead on cancel; email preview shows "[private PIN]"; **"Send a new PIN"** updates the invitation (an old PIN can never be shown). Stops link-only leaks; a forwarded email still carries both, which the face check covers.
- **Join check:** after the PIN and consent, a **guided capture**: an oval on the camera preview, live tips ("Move closer", "Face the light", "Look straight", "Hold still", "Only one person"), checked in the browser with **MediaPipe Face Landmarker** (served from our app; nothing leaves the browser), border turns **green** when the face is right; the one good photo goes to the backend, is matched with **OpenCV YuNet + SFace** against the invited candidate **and** the job's other applicants, then discarded.
- **Never blocks (owner's rule):** every candidate can join whatever the score. The result is **interviewer-only** (the candidate sees "Thanks, you're all set"): ✅ Identity verified / ⚠️ Low match: check identity / ❗ Very low match (or matches another applicant): verify identity / ℹ️ Identity not checked (reason). Shown in the **waiting room** (Interviews tab) and at the top of the room's **candidate panel**. Band limits set from a test with the owner's own face.
- **F7 profile panel** in the interviewer room: identity badge, name, headline experience, key skills, pre-interview score, areas to probe.
- **Privacy (N16, N17, N19):** store only the face code and the consent time, never photos or snapshots; delete with the candidate and after the retention period; logs hold result and score only; README section (what, where, how long, nothing leaves the PC). Demo with the owner's own face (consented); sample CVs stay synthetic.
- **Free and local:** `@mediapipe/tasks-vision` (Apache 2.0), OpenCV YuNet (MIT) and SFace (Apache 2.0) via `opencv-python-headless`; CPU only; no cloud face API (InsightFace models avoided: non-commercial licence).
- **First step:** a small test script with the owner's passport photo and webcam (match scores for the owner vs another face) before building screens. UI needs mockups first (oval capture, PIN entry, labels, profile panel).
- **Open (PENDING):** Take photo button vs automatic capture after ~1 s of green · blink check (liveness) now or later · retention period (e.g. 30 days or until the job closes) · whether the photo from inside the CV is used when no form photo is uploaded.

### 5.4 Deferred items (owner: "later")
1. Remove the demo code (`routes/graphs.py`, demo part of `routes/tasks.py`, `graphs/demo.py`).
2. Phone sidebar fix (mockup needed).
3. Measure the 20-CV screening time (README; Module 9).
4. Update the High-Level and Detailed Architecture diagrams (Blogger, Google Form only, mcp-google, LiveKit, Deepgram/AssemblyAI, worker).
5. Simplify the logging code (#646546), after all other tasks.
6. README: env table (incl. STT providers and keys, LiveKit, interview settings), measured transcription delay (AssemblyAI), AssemblyAI in the third-party data list, and a "two-person demo" section.
7. Tests on one PC need headphones and one window unmuted at a time (shared mic/speaker echo).
8. Minimum experience in half years (e.g. 1.5): not supported (whole years); owner said no change for now.
9. **Same-Wi-Fi / phone-hotspot demo mode ("Way 2"):** done manually, no code: Cloudflare quick tunnels for the website (3000) and LiveKit signalling (7880); `node_ip` in `livekit/livekit.yaml` set to the PC's LAN IP (never committed; `git restore` to switch back); `FRONTEND_BASE_URL` and `LIVEKIT_URL` updated per run; firewall TCP 7881 / UDP 7882. The one-PC (incognito) setup stays the default. Different networks need Tailscale or LiveKit Cloud (not adopted).
10. Transcription "later" ideas (not required): store per-turn confidence (next free migration `0015`), keyterm spelling table (FastAPI, Kubernetes…), endpointing / turn length as settings.
11. Google STT as a third provider (PENDING).
12. **Question inferred from the candidate's answer** when the interviewer's question is lost from the transcript (owner: "keep reminding, I will tell you later"). Today such an answer is skipped.
13. **Re-evaluate** option for interviews that already have a report (offered; the API allows it, the UI does not). Workaround: `POST /interviews/{id}/evaluate` from `/docs`.
14. Hire / Hold / Reject decision: endpoint and timing PENDING.

### 5.5 Known limitations (for the README)
- Gemini 3.5 Flash-Lite ignores temperature; repeated scoring can differ by up to ~2 final-score points.
- The Google sign-in (Testing mode) expires about every 7 days.
- "New applications waiting" count can be wrong after form responses are deleted.
- Free-tier LLM limits bound screening speed.
- Two-window tests on one PC duplicate or garble the transcript (shared microphone and speakers).
- Short pauses split an answer into several transcript lines (both providers).
- Lower-case job keywords can make technical words appear in lower case ("fastapi").
- AssemblyAI's free plan cannot opt out of model training; its EU data zone returned no text in testing.
- Candidates can only join from the same PC for now (remote join is the planned "Way 2" demo mode).
- The waiting-candidates count is cached for about 2 minutes.
- Evaluation needs the AI service: if Gemini is down after its retries, the evaluation stops with a message and can be run again.
- An answer whose question was lost from the transcript is not evaluated (deferred item 12).
- Speech-to-text is set up for English; mixed-language answers give weaker transcripts and scores.
- Very long interviews (over about 2 hours of text) are cut for segmentation.
- The AI may classify a question's kind imperfectly (for example technical vs behavioural); the Q&A tab shows it.
- Areas to verify and evidence gaps are saved with the report; reports written before a rule change keep their old lists until written again.

---

## 6. Working agreement with Claude (both accounts)

- **Per step:** share understanding and questions first (with mockups on the design canvas for any UI) → build only after the owner confirms → deliver `hirelucent_step_X.zip` (changed files with repo paths; corrected re-sends get a new name such as `_v2`) with apply commands, a test checklist ending with "Done when", small commits with Refs/Closes, and the push command → after the owner pushes, verify GitHub against the delivered files → give the Redmine notes.
- **Redmine timing:** each task's description comes together with its daily note; a feature's description once all its tasks are done; a module's description once all its features are done. Work without its own task uses the closest existing task (`Refs`, no new task).
- **Docs:** `project_context.md` and `HANDOFF.md` are updated only when a module is complete (always) or when the owner asks; in between, Claude keeps a list of pending changes.
- **Explanations:** keep them simple and short; recommend the minimum that meets the requirements when time is tight.
- **Apply commands (from the project folder):**
  ```
  rm -rf ~/Downloads/hirelucent_step_X
  unzip -o ~/Downloads/hirelucent_step_X.zip -d ~/Downloads
  cp -r ~/Downloads/hirelucent_step_X/. .
  docker compose up -d --build
  ```
- **Tests:** `cd backend && source .venv/Scripts/activate && python -m pytest -q && cd ..` (602 tests at `0bee242`; on the Windows venv a few are skipped (Tesseract, `livekit`); the first run on Windows takes 1–2 minutes, do not interrupt it). Frontend: `npm run lint`, `npm run build`. Use forward slashes in Git Bash paths.
- **pgAdmin (optional):** `docker compose --profile tools up -d pgadmin` → http://localhost:5050; needs `PGADMIN_EMAIL` / `PGADMIN_PASSWORD` in that PC's `.env`.
- **Commits:** `<type>(<scope>): <Summary>` (≤50 chars, imperative), body bullets "- " wrapped at 72, footer `Refs #id` or `Closes #id`; multiline `git commit -m … -m …`, then `git push origin <branch>`. **Claude never commits or pushes; the owner does.**
- **Redmine:** Textile. Daily notes `h1. *Date: dd/mm/yy*` + past-tense bullets, only work actually done; descriptions = one paragraph + `*Outcomes:*` bullets.
- **DB check shortcut (Git Bash):** `hdb() { docker compose exec -T postgres sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"' <<< "$1"; }`
- **Security:** never commit `.env` or `secrets/`; never paste keys in chat; no personal data in repo or logs; external actions only after HITL.
