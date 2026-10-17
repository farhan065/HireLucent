# HireLucent: Project Context

> **Status labels:** **BUILT** = implemented, tested and pushed · **FINAL** = agreed, do not change unless the owner asks · **PROPOSED** = suggested design, confirm before major work · **PENDING** = owner decides later · **Not specified** = no information yet.
> Anything not marked **BUILT** is not in the code yet. For BUILT parts, the names in this file are the names used in the code. If the code and this file ever differ, **the code wins**; tell the owner which lines of this file to correct.
> **Last updated:** 16 Oct 2026, Module 5 in progress (steps 5.0–5.5 BUILT and pushed; next is step 5.6, the transcript viewer). Branch `module/5-transcription`, last commit `ba37bd4`.

---

## 1. Project overview

**HireLucent** is an AI-powered recruitment and interview platform (BJIT Academy AI Trainee final project, solo work by Shahriar Farhan, **due 27 Oct 2026**). It covers hiring end to end:
JD creation → job posting → CV collection → screening and ranking → scheduling → live video interview with transcription → assessment → ranked list → human decision.

**Core principle:** AI assists, people decide. Every score or flag must be traceable to CV or transcript evidence, and human-in-the-loop (HITL) approval gates all external or consequential actions.

### 1.1 Mandatory stack and rules
- Python 3.10+ (container uses 3.11), **FastAPI + Pydantic** (OpenAPI docs), **LangGraph** (real multi-node stateful graphs with retries and checkpointing), **Docker Compose** (single-command startup `docker compose up -d --build`, named volumes, `.env.example`, clean-machine reproducible), GitHub (incremental commits).
- **Repo branching (FINAL):** `main` + `dev` + one branch per module (`module/2-foundation-setup`, `module/3-pre-interview-core`, `module/4-video-interview`, `module/5-transcription`, …). A module branch is merged into `dev` by pull request when the module is complete; the next module branch is created from `dev`. `main` is merged **once**, after `dev` is fully complete.
- Local execution only. Only two roles: **Interviewer** (full access) and **Candidate** (interview only, no account).
- **Database migrations:** Alembic (FINAL), migrations `0001`–`0013` so far (the next one is `0014`).
- **Code style (FINAL):** simple and easy to explain, never at the cost of requirements, quality or industry standards. Small, frequent commits in the format `<type>(<scope>): <Summary>`.

### 1.2 Scope
- **Core features (mandatory):**
  - **F1** CV screening and semantic ranking with met / partly met / not met evidence; candidates failing any must-have are excluded. **BUILT** (Module 3).
  - **F2** 0–100 scoring with per-dimension breakdown and justification. **BUILT** (Module 3).
  - **F3** 1-on-1 browser video interview with full lifecycle, controls and auto-reconnect. **BUILT** (Module 4).
  - **F4** live transcription, speaker-attributed through separate audio channels, with timestamps, saved incrementally. **Mostly BUILT** (Module 5; viewer and robustness still to do).
  - **F5** Q&A analysis (Module 6). **F6** consolidated assessment with export and traceability (Module 6).
- **Client changes (override the BID):** the chatbot posts JDs to a portal with an API → **Blogger careers page** (BUILT); CVs arrive via **Google Form only for now** (BUILT; Gmail intake only if necessary, FINAL); future-dated interview scheduling is required (BUILT).
- **Stretch (only after all core features work):** F7–F10. F7 is not required this phase.
- **Innovation (exactly one):** Candidate Feedback Composer (initial choice, §4.8).
- **Out of scope:** cloud deployment/CI-CD, SSO, ATS/HRIS, offers/onboarding, multi-tenancy, mobile, model training.

### 1.3 Key constraints
- **Performance:** 20 CVs screened in about 5 minutes (state the measured time in README). **Not measured yet** (deferred). Screening runs at most 4 CVs at a time. AI pacing: 14 requests/minute overall, background screening capped at 10/minute, so the interviewer's chat stays responsive. One live interview plus background processing at the same time (checked in 4.10).
- **Security:** secrets only in `.env` (never committed, never pasted in chat); validate inputs, file types and sizes (PDF/DOCX, 10 MB); candidates can never reach scores, rankings, reports or the transcript (403 / interviewer-only data); no stack traces or prompts in error responses.
- **Privacy:** sample or synthetic CVs only; no personal data in the repo or logs; **raw audio/video never stored**; transcript text never logged; Deepgram is asked not to keep audio for model training (`mip_opt_out=true`); candidate emails, phones and links never reach the LLM (masked in every prompt; the agent sees IDs and names only); README lists third-party services that receive candidate data (Gemini: CV text with contacts masked; Deepgram: interview audio; Google: name/email for the calendar invitation); candidate deletion endpoint; English only.
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
  - Each stream goes to a **Deepgram** live connection (`nova-3`, English, interim results, smart format, endpointing 300 ms, utterance end 1000 ms, `mip_opt_out=true`, optional job **keyterms**). Keep-alive during silence; reconnect with growing waits (1 s → 30 s) and up to 30 s of queued audio.
  - Final pieces are joined into a **turn** at each pause (or after 30 s) and **saved immediately** to `transcript_turns` (speaker, `start_ms`, `end_ms` from the interview start, text). An audio clock corrects times after muted gaps. Overlapping speech = separate entries per speaker.
  - **Live push (FINAL: option A):** the worker sends `live` (words still being spoken), `turn` (each saved turn with its id) and `status` (`listening` / `paused` / `off`, every 5 s) over LiveKit data, **to the interviewer only**. LiveKit blanks the sender identity for hidden participants, so the browser accepts transcript data only from a sender with **no identity** (the candidate cannot fake lines).
  - **Live transcript panel (FINAL):** newest line at the bottom, auto-scroll that pauses when scrolling up + "N new · Jump to latest"; **one row per turn** (not grouped) with avatar ("You" / candidate initials), name ("You" / candidate's first name), time from the start (clock time on hover); grey interim words with "●●● speaking"; states Not started / Loading / Listening / Paused (banner "Transcription paused, reconnecting…") / Not available (no status for 15 s or speech-to-text off). Saved turns load first and after every reconnect.
  - Settings: `STT_PROVIDER` (`deepgram` | `off`), `DEEPGRAM_API_KEY`, `STT_KEYTERMS` (`true` | `false`). Provider is a switch so Google STT can be added later (PENDING).
  - `GET /interviews/{id}/transcript` (interviewer only): ordered turns with `start_ms`, `end_ms`, `spoken_at` (clock time), text.

**Step 10: Interview ends.** `POST /interviews/{id}/end` → room closed → worker saves the last words → status `completed`, `ended_at` set → candidate link and passes stop working.

### Stage 4: Assess and decide (PROPOSED, Module 6: F5, F6)

**Step 11: Post-interview assessment.** Evaluate → EvaluationService runs the **Q&A Analysis graph** (loads the transcript from PostgreSQL, ends by adding new questions to `question_bank`) then the **Final Assessment graph** (HITL report review) → saved assessments, status `assessed`.

**Step 12: Final ranked candidate list** (read-only, no LLM): ranking, comparison and PDF/HTML export built on request, not stored. A full candidate report page belongs here (F6).

**Step 13: Decision:** Hire / Hold / Reject (`PATCH /candidates/{id}`, columns exist, endpoint not built). Candidate Feedback Composer starts here.

---

## 3. Technical architecture

### 3.1 Components

| Component | Technology | Status |
|---|---|---|
| Frontend | React 19 + Tailwind CSS v4 + Vite, React Router, lucide-react, react-markdown, `livekit-client`; fonts Plus Jakarta Sans and Figtree; ESLint (react-hooks v7); code formatted Prettier-style (no semicolons, single quotes, width 100) | BUILT |
| Backend | FastAPI + Pydantic v2, SQLAlchemy 2, Alembic | BUILT |
| Services | auth, chat (+ conversation store/view), knowledge, job, job_post, job_deletion, intake (google_forms, google_drive, google_client), screening, shortlist, task, blogger, text_extraction, **session, scheduling, interview_emails, interview_times, interview_context, join, room, video, question, interview_chat, transcript** | BUILT |
| AI workflows | LangGraph + PostgresSaver | Recruiter Agent, CV Screening BUILT; Q&A, Final Assessment later |
| MCP clients | `app/mcp_clients/registry.py` (`mcp_servers()`: rag offered to the agent; google and blogger backend-only with `allowed_tools`) + `app/mcp_clients/client.py` (`call_tool`, `agent_tool_definitions`, `call_agent_tool`) | BUILT |
| MCP servers | **mcp-rag** (custom, port 8001: `search_jd_references`, `search_question_bank`), **mcp-blogger** (zachsladecode/blogger-mcp-server, pinned, supergateway, port 8002: `create_post`), **mcp-google** (custom, port 8003: `send_email`, `create_calendar_event`, `update_calendar_event`, `cancel_calendar_event`) | BUILT |
| Relational DB | PostgreSQL 16 | BUILT |
| Vector DB | ChromaDB 1.5 (cosine) | BUILT |
| Embeddings | `qwen3-embedding:0.6b` via Ollama (temporary; OpenAI selectable) | BUILT |
| LLM | Gemini 3.5 Flash-Lite free tier (OpenAI selectable); pacing 14/min, background 10/min; retries; room chat has shorter timeouts (`ROOM_AI_*`) | BUILT |
| Video | Self-hosted LiveKit (`livekit/livekit-server:v1.13.7`) | BUILT |
| Speech-to-text | **Deepgram nova-3** live streaming (FINAL for now); Google STT later via `STT_PROVIDER` (PENDING) | BUILT |
| Google APIs | One Cloud project: Forms, Drive (direct), Blogger (MCP), Calendar + Gmail send (mcp-google) | BUILT |
| CV parsing / OCR | PyMuPDF, python-docx, Tesseract | BUILT |

### 3.2 Docker Compose services (BUILT)
`postgres`, `backend`, `frontend` (nginx), `mcp-rag`, `mcp-google`, `mcp-blogger`, `livekit`, `transcription-worker` (shares the livekit network: `network_mode: service:livekit`), `chromadb`, `ollama` + `ollama-pull`. One `docker-compose.yml`. `./secrets` (git-ignored) holds the Google files; `./logs` bind mount.

### 3.3 Authentication and roles
| Token | Holder | Scope |
|---|---|---|
| App JWT | Interviewer | All interviewer APIs, 60 min |
| Join link token | Candidate | Only its SHA-256 hash stored; finds the interview |
| Candidate pass (JWT) | Candidate | One interview (role, session_id, link fingerprint) |
| LiveKit token | Interviewer, candidate, worker | One room `interview-<id>`; worker's is hidden, no audio/video publishing |

### 3.4 Data stores
**PostgreSQL tables (BUILT):** `users`, `jobs`, `candidates`, `screening_results`, `removed_applications`, `conversations`, `documents`, `tasks`, `interview_sessions` (times, join token hash, calendar event id, status `scheduled`/`in_progress`/`completed`/`cancelled`, joined/started/ended/consent/cancelled times, `candidate_seen_at`, `suggested_questions` JSONB, `created_by`), `transcript_turns` (session_id, speaker `interviewer`/`candidate`, start_ms, end_ms, text), `assessments` (FINAL Option A schema, used from Module 6), LangGraph checkpoint tables.
**Candidate statuses:** `applied`, `screening_failed`, `excluded`, `screened`, `shortlisted`, `selected` (unused), `interview_scheduled`, `assessed`.
**Never stored:** raw audio/video, live messages, join tokens (only hashes), JWTs, LiveKit tokens.

### 3.5 UI design
> - The owner wants a **very professional, modern and beautiful UI**.
> - **Before implementing any UI screen or change: share the understanding, show a mockup on the design canvas, wait for approval, then apply it exactly.**
> - Design canvas: https://claude.ai/artifact/1YsLaBugibMF1nbsWtcWYj (all approved mockups; Module 5 boards: `M5LiveTranscript`, `M5TranscriptStates`).

Theme (FINAL): clean corporate SaaS, white/pale-blue backgrounds, blue primary `#1557E0`, navy headings `#0B1F4B`, body text `#51607A`, rounded cards, subtle shadows; each stage its own colour (no dark navy fills). Tailwind tokens in `frontend/src/index.css` (brand, navy, body, mist, tint, line, success, warning, danger, teal, amber, violet + `-soft`).

**Screens (BUILT):** landing, login, sidebar (Dashboard, Jobs, AI Agent, Knowledge Base), Dashboard, Jobs page, job page tabs (Job post, Applications, Screening, **Interviews**), AI Agent page (cards, job brief), Knowledge Base, interviewer room `/app/interviews/:sessionId/room`, candidate pages `/interview/:token` (pre-join, waiting, room, ended).
**Next screen (5.6):** transcript viewer for completed interviews (mockup first).

---

## 4. Implementation details

### 4.1 LangGraph workflows
**LangGraph 1: Recruiter Agent** (BUILT, `app/graphs/recruiter/`): nodes `load_context`, `agent`, `human_approval` (interrupt), `call_tools`, `handle_error`, `respond`. Tools: RAG MCP `search_jd_references` (read-only, via `call_agent_tool`), `SaveJob`, `PublishJob`, `GetCandidates` (read-only), `ScheduleInterviews`, `RescheduleInterview`, `CancelInterview` (HITL). PREPARERS build approved details from app data; invalid tool details go back to the model to fix. Threads: one per job conversation; `interview-<id>` for the read-only room chat (interview mode).
**LangGraph 2: CV Screening** (BUILT, `app/graphs/screening/`): per-CV branches (max 4), resume-from-step, `extract_text` → `run_ocr` → `parse_cv` → `check_must_haves` (FINAL option B) → `match_requirements` → `compute_ats_score` → `score_candidate` → `save_result`; `log_failure`; `rank_candidates` (never shortlists).
**LangGraph 3: Q&A Analysis** and **LangGraph 4: Final Assessment**: PROPOSED (Module 6), designs unchanged (see the .drawio diagrams).

### 4.2 RAG design (BUILT parts)
Collections: `jd_references`, `cv_embeddings`, `question_bank` (with roles), `rag_documents`. Collections are fixed in code, never chosen by the LLM. `QUESTION_BANK_MAX_DISTANCE` and `JD_REFERENCE_MAX_DISTANCE` (0.6).

### 4.3 Tools and MCP
| Tool | Type | HITL | Status |
|---|---|---|---|
| `search_jd_references`, `search_question_bank` | RAG MCP | No | BUILT |
| `verify_answer` | RAG MCP | No | Later (Module 6) |
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
- **Later:** evaluate, ranking, compare, export, decision (Module 6+).

### 4.6 Error handling and logging
JSON logs (IDs and numbers only: no names, emails, CV text, transcript text, tokens, keys or prompts). Worker events: `interview_audio_joined`, `stt_connected`, `transcript_turn_saved` (speaker, times, word count), `stt_stream_finished`, `stt_refused`, `stt_disconnected`, `stt_not_configured`. PENDING: simplify the logging code after all other tasks.

### 4.7 Innovation feature: Candidate Feedback Composer (initial choice, Module 7)
After Hold/Reject: draft respectful feedback from saved job-related evidence only, fairness check, HITL edit/approve, send via `send_email`. Graph, endpoint, UI and the 300–500 word rationale (owner's own reasoning) not yet specified.

---

## 5. Development status (16 Oct 2026)

### 5.1 Redmine tree and status
- **Module 2** Foundation: BUILT, merged into `dev`.
- **Module 3** (Story #647080, F1 + F2): BUILT, merged into `dev`.
- **Module 4** (Story #648326, F3): **all tasks done**, merged into `dev` (14 Oct).
  - Feature 17 #648327: #648332, #648333, #648334, #648335 · Feature 18 #648328: #648336, #648337, #648338 · Feature 19 #648329: #648340, #648341 · Feature 20 #648330: #648342 · Feature 21 #648331: #648343
- **Module 5** (Story #648345, F4), branch `module/5-transcription`:
  - Feature 22 Speech-to-Text #648346: #648360 ✅, #648362 ✅ (feature complete)
  - Feature 23 Speaker Attribution & Timestamping #648347: #648363 ✅, #648365 ✅ (complete)
  - Feature 24 Structured Transcript & Persistence #648349: #648367 ✅, #648369 ✅ (complete)
  - Feature 25 Live Transcript Display #648354: #648372 ✅, #648374 ✅ (complete)
  - Feature 26 Transcript Viewer #648355: **#648375 — next (step 5.6)**
  - Feature 27 Transcription Robustness #648357: **#648376 — step 5.7**

### 5.2 Module 5 step log
| Step | Content | Commits | Status |
|---|---|---|---|
| 5.0 | Editable email message (+ preview endpoint), GetCandidates, Edit message on cards/dialogs, real camera/mic errors | `5710edf`, `1ed6036`, `08cfc03`, `a8710a7` (Refs #648332/#648335/#648336) | ✅ |
| 5.0b/c | Agent uses the shared MCP client (old `app/rag/mcp_client.py` removed); delete job blocked with upcoming interviews; unused helper removed | `33244df`, `a50e20c`, `82ddd7e` | ✅ |
| 5.1 + 5.2 | Deepgram streaming per speaker, settings, turns saved with times, transcript API | `26b094d`, `d668f99`, `9d97510` | ✅ |
| 5.3 + 5.4 + 5.5 | Live push to the interviewer, live transcript panel, Paused/Not available states | `0f79306`, `ba37bd4` | ✅ |
| **5.6** | **Transcript viewer for completed interviews (#648375)** | — | **Next** |
| 5.7 | Robustness (#648376): silence, overlap, accents, low confidence; measure delay; possible tuning (endpointing 300 → 500–700 ms, keyterms with proper capitals), quality/speed review | — | Pending |
| End | Full test, Redmine feature/module descriptions, merge Module 5 into `dev` | — | Pending |

### 5.3 Step 5.6 plan (PROPOSED, waiting for the owner)
- Interviews tab → each **Completed** interview gets **View transcript** → opens the viewer.
- Viewer: header (candidate, job, date, length); **search** with highlighted matches, next/previous and "3 of 12"; **timestamp navigation** (timeline with minute markers, clickable times); turns in the same one-row-per-turn style; read-only, interviewer only; uses the existing `GET /interviews/{id}/transcript`.
- **Open questions for the owner:** (1) full page (recommended) or side panel; (2) Download (.txt) button or not. Mockup on the design canvas before building.

### 5.4 Deferred items (owner: "later")
1. Remove the demo code (`routes/graphs.py`, demo part of `routes/tasks.py`, `graphs/demo.py`).
2. Phone sidebar fix (mockup needed).
3. Measure the 20-CV screening time (README; Module 9).
4. Update the High-Level and Detailed Architecture diagrams (Blogger, Google Form only, mcp-google, LiveKit, Deepgram, worker).
5. Simplify the logging code (#646546), after all other tasks.
6. README: env table (incl. Deepgram/STT, LiveKit, interview settings) and a "two-person demo" section.
7. Transcript quality and speed review (5.7). Tests on one PC need headphones and one window unmuted at a time (shared mic/speaker echo).
8. Minimum experience in half years (e.g. 1.5): not supported (whole years); owner said no change for now.
9. Google STT as a second provider (PENDING).

### 5.5 Known limitations (for the README)
- Gemini 3.5 Flash-Lite ignores temperature; repeated scoring can differ by up to ~2 final-score points.
- The Google sign-in (Testing mode) expires about every 7 days.
- "New applications waiting" count can be wrong after form responses are deleted.
- Free-tier LLM limits bound screening speed.
- Two-window tests on one PC duplicate or garble the transcript (shared microphone and speakers).
- The waiting-candidates count is cached for about 2 minutes.

---

## 6. Working agreement with Claude (both accounts)

- **Per step:** share understanding and questions first (with mockups on the design canvas for any UI) → build only after the owner confirms → deliver `hirelucent_step_X.zip` (changed files with repo paths; corrected re-sends get a new name such as `_v2`) with apply commands, a test checklist ending with "Done when", small commits with Refs/Closes, and the push command → after the owner pushes, verify GitHub against the delivered files → give the Redmine notes.
- **Apply commands (from the project folder):**
  ```
  rm -rf ~/Downloads/hirelucent_step_X
  unzip -o ~/Downloads/hirelucent_step_X.zip -d ~/Downloads
  cp -r ~/Downloads/hirelucent_step_X/. .
  docker compose up -d --build
  ```
- **Tests:** `cd backend && source .venv/Scripts/activate && python -m pytest -q && cd ..` (401 passing at `ba37bd4`). Frontend: `npm run lint`, `npm run build`.
- **Commits:** `<type>(<scope>): <Summary>` (≤50 chars, imperative), body bullets "- " wrapped at 72, footer `Refs #id` or `Closes #id`; multiline `git commit -m … -m …`, then `git push origin <branch>`. **Claude never commits or pushes; the owner does.**
- **Redmine:** Textile. Daily notes `h1. *Date: dd/mm/yy*` + past-tense bullets, only work actually done; descriptions = one paragraph + `*Outcomes:*` bullets.
- **DB check shortcut (Git Bash):** `hdb() { docker compose exec -T postgres sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"' <<< "$1"; }`
- **Security:** never commit `.env` or `secrets/`; never paste keys in chat; no personal data in repo or logs; external actions only after HITL.
