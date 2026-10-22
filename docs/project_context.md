# HireLucent: Project Context

> **Status labels:** **BUILT** = implemented, tested and pushed · **FINAL** = agreed, do not change unless the owner asks · **PROPOSED** = suggested design, confirm before major work · **PENDING** = owner decides later · **Not specified** = no information yet.
> Anything not marked **BUILT** is not in the code yet. For BUILT parts, the names in this file are the names used in the code. If the code and this file ever differ, **the code wins**; tell the owner which lines of this file to correct.
> **Last updated:** 22 Oct 2026, **Module 7 (F11, Candidate Feedback Composer) complete** on `module/7-innovation` (last F11 commit `4d9838d`, then the F7 fix `567d058`; PR into `dev` next). Module 8 Stretch 1 (F7) is merged into `dev` (PR #6). Next: the remaining stretch features F8–F10, each in its own chat and branch. F11 details in §5.7, F7 in §5.6.

---

## 1. Project overview

**HireLucent** is an AI-powered recruitment and interview platform (BJIT Academy AI Trainee final project, solo work by Shahriar Farhan, **due 27 Oct 2026**). It covers hiring end to end:
JD creation → job posting → CV collection → screening and ranking → scheduling → live video interview with transcription → assessment → ranked list → human decision.

**Core principle:** AI assists, people decide. Every score or flag must be traceable to CV or transcript evidence, and human-in-the-loop (HITL) approval gates all external or consequential actions.

### 1.1 Mandatory stack and rules
- Python 3.10+ (container uses 3.11), **FastAPI + Pydantic** (OpenAPI docs), **LangGraph** (real multi-node stateful graphs with retries and checkpointing), **Docker Compose** (single-command startup `docker compose up -d --build`, named volumes, `.env.example`, clean-machine reproducible), GitHub (incremental commits).
- **Repo branching (FINAL):** `main` + `dev` + one branch per module (`module/2-foundation-setup`, `module/3-pre-interview-core`, `module/4-video-interview`, `module/5-transcription`, `module/6-assessment`, …). A module branch is merged into `dev` by pull request when the module is complete; the next module branch is created from `dev`. `main` is merged **once**, after `dev` is fully complete.
- Local execution only. Only two roles: **Interviewer** (full access) and **Candidate** (interview only, no account).
- **Database migrations:** Alembic (FINAL), migrations `0001`–`0016` so far (`0014` adds `assessments.question_suggestions`; `0015` adds the F7 face, PIN and identity columns; `0016` adds the F11 `candidate_feedback` table and clears old `hold` decisions; the next one is `0017`).
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
- **Stretch (only after all core features work):** F7–F10, one branch per stretch feature (`module/8-stretch-<n>-<feature>`). **F7 BUILT** (Module 8 Stretch 1, 20 Oct, §5.6). Clarification #21 says face or voice recognition is "not required in this phase"; the owner went beyond it with face verification and **the trainer approved it** (20 Oct). Module 7 innovation is done (22 Oct); F8–F10 next.
- **Innovation (exactly one):** **F11 Candidate Feedback Composer, BUILT** (Module 7, 22 Oct, §4.7 and §5.7).
- **Out of scope:** cloud deployment/CI-CD, SSO, ATS/HRIS, offers/onboarding, multi-tenancy, mobile, model training.

### 1.3 Key constraints
- **Performance:** 20 CVs screened in about 5 minutes (state the measured time in README). **Not measured yet** (deferred). Screening runs at most 4 CVs at a time. AI pacing: 14 requests/minute overall, background screening capped at 10/minute, so the interviewer's chat stays responsive. One live interview plus background processing at the same time (checked in 4.10).
- **Security:** secrets only in `.env` (never committed, never pasted in chat); validate inputs, file types and sizes (PDF/DOCX, 10 MB); candidates can never reach scores, rankings, reports or the transcript (403 / interviewer-only data); no stack traces or prompts in error responses.
- **Privacy:** sample or synthetic CVs only; **biometric data (F7):** the application photo (re-saved JPEG, random name) and its face code are kept only for the identity check and deleted with the candidate or job; the photo taken when joining and camera frames are never stored; no face goes to any external service (models run locally); consent at application and at joining; no personal data in the repo or logs; **raw audio/video never stored**; transcript text never logged; transcript text sent to Gemini for evaluation has contacts masked; report PDF file names carry no candidate name; Deepgram is asked not to keep audio for model training (`mip_opt_out=true`); AssemblyAI (optional second provider) cannot opt out of model training on the free plan, so it is used with test interviews only; candidate emails, phones and links never reach the LLM (masked in every prompt; the agent sees IDs and names only); README lists third-party services that receive candidate data (Gemini: CV text with contacts masked; Deepgram or AssemblyAI: interview audio; Google: name/email for the calendar invitation); candidate deletion endpoint; English only.
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

**Step 3: The agent posts the job.** Asks for the Google Form link → backend checks it (readable, required questions incl. a required **photo** upload and a required **consent** question (F7), one form per job) → post preview card → `PublishJob` (HITL) → backend calls Blogger MCP `create_post` → `jobs.status = published`, links saved.

**Step 4: Candidates apply** through the job's Google Form: full name, email, CV upload, a recent passport-size **photo** (title contains "photo"; asked to be under 3 months old) and a **consent** checkbox (title contains "consent"), all required. Questions are found by a word in their title.

### Stage 2: Screen and shortlist (BUILT)

**Step 5: Fetch CVs** (Applications tab, `POST /jobs/{id}/intake`, background task, no LLM): Forms API → Drive download → `candidates` rows (status `applied`), skip duplicates and deleted applicants (`removed_applications`). **F7 enrolment** (`intake_service.enrol_face`): with consent, the photo is checked in memory (one face, ≥ 60 px, sharp and light enough), re-saved as a JPEG ≤ 800 px under `<cv dir>/<job>/photos/<random>.jpg` and turned into an SFace face code; `face_status` = `enrolled` / `photo_unusable` (+ `face_problem`) / `no_photo` / `no_consent`. A photo problem never stops the application. Face status is not shown on the Applications tab (owner: maybe later). "New applications waiting" count (count-based; known limitation).

**Step 6: Screen CVs** (Screening tab, `POST /jobs/{id}/screen`) → CV Screening graph (§4.1). Results: requirement matches with evidence, match ranking, dimension scores, ATS score, final score (0.8 × criteria + 0.2 × ATS), final ranking, summary, exclusion reasons, CV facts. Two sub-tabs (Requirement match / Final ranking), Show dropdown, search, expandable rows.
- **Human step (FINAL): no automatic shortlist.** Shortlist one by one, by top N or by minimum score; clear the shortlist. **The shortlist is the selection for interview (FINAL):** shortlisted candidates are scheduled directly; status `selected` stays unused.
- **Rejected at screening (F11, FINAL):** everyone not shortlisted (`screened`, `excluded`, `screening_failed`) counts as rejected and gets a feedback email (§4.7). They can still be shortlisted until that email is sent; then shortlisting is locked for them, and shortlisting removes an email not sent yet. The Final ranking shows a **Status** column (Rejected, Shortlisted, Interview scheduled, Interviewed, Hired, Rejected after interview) and a **Feedback email** column; a third sub-tab **Feedback emails** lists everyone rejected at screening. Unranked rows show only the arrow and the name; the reason is in the opened box.
- Candidate delete at any stage removes the candidate, CV file and vectors. Screening reset when requirements change (not allowed once interviews exist).

**Step 7: Schedule the interview (BUILT, Module 4)**
- **Two ways (FINAL):** (a) the **AI Agent** conversation: tools `GetCandidates` (read-only; lists ranked candidates with status and interview status), `ScheduleInterviews`, `RescheduleInterview`, `CancelInterview` (all three HITL cards with an email preview); (b) the job's **Interviews tab**: schedule form (candidates, date, time, length 30/45/60, break), reschedule and cancel with confirm dialogs.
- If a candidate is not shortlisted, the agent tells the interviewer to shortlist them on the Screening tab first (no shortlisting from the chat).
- **Email (FINAL):** the candidate gets **only Google Calendar's invitation** (created by the `mcp-google` server with `sendUpdates="all"`): invitation, updated invitation on reschedule, Google's cancellation notice. Title "HireLucent video interview – <job>". Description order: Hello → **editable message** → When → **Join link** and **Interview PIN** right under it → tips (incl. the PIN and the identity photo) → signature "HireLucent Careers". The interviewer can edit the message paragraph on all cards and dialogs (or by typing in the chat); `POST /jobs/{id}/interviews/preview` shows the exact email with "[private link]" and "[private PIN]" (kinds `invitation`, `moved`, `cancelled`, `new_pin`).
- **Rules:** times stored in UTC; screens show the browser's local time; the agent reads typed times in `APP_TIMEZONE` (default Asia/Dhaka); minimum notice `INTERVIEW_MIN_NOTICE_MINUTES` (15; 1 while testing); no overlapping interviews for the same interviewer. Candidate status → `interview_scheduled`.
- Interviews tab lists Upcoming / Completed / Cancelled (pills); cancelled rows can be deleted from history. Candidates with an interview show "Interview scheduled" + See interview on the candidate lists. Deleting a job is blocked while it has upcoming interviews.

### Stage 3: Live interview (BUILT, Modules 4–5)

**Step 8: Candidate joins (no account)**
- Link `/interview/<token>`: `secrets.token_urlsafe(32)`, **only its SHA-256 hash is stored**; new link on reschedule, old link dead on reschedule/cancel.
- **Three tokens:** (1) the join link token (proves the invitation); (2) the **candidate pass**, a JWT from `core/security.create_access_token` with role, session_id and link fingerprint, checked by `api/deps.require_candidate`; (3) the **LiveKit room token** for room `interview-<id>`, checked by the LiveKit server.
- **Interview PIN (F7):** 8 digits, made at scheduling, only its Argon2 hash stored; 5 wrong tries lock the link for 15 min; new PIN on reschedule; **New PIN** on scheduled rows of the Interviews tab sends an updated invitation with a **new link and PIN** for the same time (only the link's hash is stored, so the old link cannot be re-sent).
- Pages: **PIN page** (F7, interviews with a PIN) → pre-join (job, local time, camera/mic test, **consent**, incl. the identity photo; button "Continue") → **"Confirm it's you" photo step** (F7) → **waiting room** (heartbeat every few seconds; "Candidate waiting" on the Interviews tab, gone ~15 s after leaving) → room after **Admit**. Join opens `JOIN_OPENS_MINUTES_BEFORE` (10; 60 while testing) before the start. After end/cancel: "interview has ended" page.
- Endpoints: `POST /join/info` (+ `pin_required`), `/join/pin`, `/join/enter` (PIN in the body; returns `photo_needed`), `/join/identity` (one JPEG/PNG, multipart), `/join/identity/skip`, `GET /join/status`, `POST /join/leave`, `/join/room`.
- **Identity photo step (F7):** oval on the camera preview with one tip at a time (put your face in the oval / only one person / move back / move closer / centre / look straight / too dark), checked ~8×/s in the browser with **MediaPipe FaceDetector** (BlazeFace short range, served from our app by `frontend/scripts/face-guide-files.mjs`); green border → photo after **5 s of green** or **Take photo**. The backend checks it again (YuNet), compares it with the invited candidate's face code and the job's other applicants (SFace), saves only the result and discards the photo. Unusable photo → "try again" (3 tries), then "Continue to the waiting room"; no camera → continue. The candidate only sees "Thanks, you're all set" / "Photo skipped". **Never blocks.** Bands: verified ≥ 0.50, low ≥ 0.363, very low below; **another applicant** when one scores ≥ 0.50 and higher than the invited one; not checked (reason). Bands set from the owner's face test (same person 0.58–0.63, other 0.30).

**Step 9: Video interview with live transcription**
- **Video (FINAL):** self-hosted **LiveKit** (`livekit` container, ports 7880/7881/7882 udp), `livekit-client` in the browser. Interviewer room (v7): left = candidate info / Suggested questions tabs (F7: **application photo** in place of the placeholder, click to enlarge; **Identity check** row with chip and one line; **Areas to probe** section = requirements partly met / not met; identity chip also in the Admit bar and the Interviews tab waiting row); middle = one big 16:9 video (own video as a small floating tile, swap by click) with small in-video controls, and the **Live transcript** panel below; right = **AI Agent** (read-only room chat) / **Message** (live text messages with the candidate, not stored) tabs. Candidate room: video with labelled buttons below and a Message panel (closed by default). Full screen, screen share, auto-reconnect (keeps trying while the interview runs; "Still trying" card after 30 s). The interview never ends by itself (timer turns amber after the planned end); only the interviewer ends it; the candidate's Leave keeps it running.
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

### Stage 4: Assess and decide (BUILT, Module 6: F5, F6; decision and feedback emails: Module 7, F11)

**Step 11: Evaluate the interview (BUILT).** On the job's **Interviews** tab, completed rows show **Evaluate** and the tab shows **Evaluate all (N new)**. One evaluation runs at a time as a background task with progress ("Finding the questions and answers → Judging answers and checking references → Writing the report"); one interview failing does not stop the others. `EvaluationService` runs **LangGraph 3 (Q&A Analysis)**, then **LangGraph 4 (Final Assessment)** (§4.1). An interview analysed before reports existed shows **Write report** (LangGraph 4 only). Once an interview has a report, the screens no longer offer Evaluate (the API still allows re-evaluation; a Re-evaluate option was offered and is PENDING).

**Step 12: Review the report (BUILT, HITL).** Assessment page `/app/interviews/:sessionId/assessment` with tabs **Q&A** (each question with its answer, four criteria, justification, evidence quote and accuracy source; small talk marked, follow-ups indented), **Coverage** (requirement by requirement with CV status; suggested questions to add to the bank) and **Report** (scores and label, summary, strengths and weaknesses with source chips, evidence gaps, areas to verify). The report is a **draft** until the interviewer **approves** it (confirm dialog), **requests changes** (note required, AI rewrites) or **edits** it (new summary and/or remove points; nothing can be added). Approval records who and when and marks the candidate `assessed`. **Approve all drafts** on the Assessments tab approves every waiting draft (confirm dialog).

**Step 13: Ranked list, report export and comparison (BUILT).** Job tab **Assessments**: count boxes (Strong fit, Possible fit, Not a fit, Waiting for your review), filters, ranked rows (overall score desc, then interview score, then name; drafts marked) with an arrow to show the score parts and coverage; unranked rows (no overall score) below, latest first, with the reason. **Print** and **Download PDF** on the Report tab. Tick up to **3** ranked candidates → **Compare** page `/app/jobs/:jobId/compare?ids=…` (scores and requirements side by side, best value highlighted, no highlight when all are equal). Job tabs Interviews and Assessments get a green tick when their step is finished (§3.5).

**Step 14: Decision (BUILT, F11).** **Hire or Reject only (FINAL; Hold removed).** Allowed only once the report is approved: per row on the Assessments tab, on the assessment page's **Decision** tab, or by **Decide by rule** (hire the top N or everyone from a minimum overall score, the rest of the ranked candidates rejected). A decision can change (or be taken back) until its email is sent; a change removes an email not sent yet. The Assessments list has 8 columns (Compare, Rank, Candidate, Overall with CV · Interview, Report, Decision, Feedback email, Action), no sideways scroll at laptop width, and an opened row shows three summary cards (Score; In short: 2 strengths and 1 weakness; To check, with **Open the full report →**).

**Step 15: Feedback emails (BUILT, F11).** **Write emails** writes each candidate's email with LangGraph 5 (§4.1) as a draft; nothing is sent until the interviewer approves it in the review panel (**Approve and send**, **Edit**, **Request changes** with a note, **Discard**, **Send anyway** after a confirm when warnings remain). **Send all passed** sends only drafts with no warnings. Sending goes through mcp-google `send_email`; a failed send shows **Not sent** with **Try again**. Buttons only (chatbot sending is future work). The Screening and Assessments job tabs show "N emails to send".

---

## 3. Technical architecture

### 3.1 Components

| Component | Technology | Status |
|---|---|---|
| Frontend | React 19 + Tailwind CSS v4 + Vite, React Router, lucide-react, react-markdown, `livekit-client`; fonts Plus Jakarta Sans and Figtree; ESLint (react-hooks v7); code formatted Prettier-style (no semicolons, single quotes, width 100) | BUILT |
| Backend | FastAPI + Pydantic v2, SQLAlchemy 2, Alembic | BUILT |
| Services | auth, chat (+ conversation store/view), knowledge, job, job_post, job_deletion, intake (google_forms, google_drive, google_client), screening, shortlist, task, blogger, text_extraction, session, scheduling, interview_emails, interview_times, interview_context, join, room, video, question, interview_chat, transcript, evaluation_service, report_pdf, **face_models, face_service, pin_service, identity_service** (F7), **feedback_service** (F11) | BUILT |
| Face matching (F7) | Backend: `opencv-python-headless` 4.14 with OpenCV Zoo **YuNet** (MIT) and **SFace** (Apache 2.0), downloaded at image build with SHA-256 check (`python -m app.services.face_models /app/models`). Browser: `@mediapipe/tasks-vision` 1.0.1 (Apache 2.0) FaceDetector, wasm and model served from `/mediapipe/`. All local, CPU only | BUILT |
| AI workflows | LangGraph + PostgresSaver | Recruiter Agent, CV Screening, Q&A Analysis, Final Assessment, **Candidate Feedback (LangGraph 5)** BUILT |
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
| Interview PIN (F7) | Candidate | Typed before joining; only its Argon2 hash stored; 5 wrong tries → 15 min lock |

### 3.4 Data stores
**PostgreSQL tables (BUILT):** `users`, `jobs`, `candidates`, `screening_results`, `removed_applications`, `conversations`, `documents`, `tasks`, `interview_sessions` (times, join token hash, calendar event id, status `scheduled`/`in_progress`/`completed`/`cancelled`, joined/started/ended/consent/cancelled times, `candidate_seen_at`, `suggested_questions` JSONB, `created_by`), `transcript_turns` (session_id, speaker `interviewer`/`candidate`, start_ms, end_ms, text); F7 columns: `candidates.photo_path`, `face_code`, `face_status`, `face_problem`, `face_consent_at`; `interview_sessions.pin_hash`, `pin_failed_attempts`, `pin_locked_until`, `identity_check` (JSONB: result, score, other_candidate_id, other_score, reason, checked_at, attempts); `candidate_feedback` (F11: one row per candidate, deleted with the candidate or job: `kind` `screening_reject`/`interview_reject`/`hire`/`cv_unreadable`, `status` `waiting_review`/`sending`/`sent`/`failed`/`discarded`, `written_by` `ai`/`template`, subject, body, `evidence` JSONB (interviewer only), `warnings` JSONB, attempts, `error_message`, `sent_anyway`, `approved_by`, `approved_at`, `sent_at`; the email address is not copied); `candidates.decision` = `hire` / `reject` (set after the interview, or `reject` when a screening rejection email is sent), `decided_by`, `decided_at`; `assessments` (one row per interview: status `analysed` → `draft` → `approved`; `qa_evaluations`, `coverage_map`, `question_suggestions` from LangGraph 3; `cv_score`, `interview_score`, `overall_score`, summary, strengths, weaknesses, gaps, `areas_to_verify` from LangGraph 4; `approved_by`, `approved_at`; the label `suitability` is computed from `overall_score`, not stored), LangGraph checkpoint tables.
**Candidate statuses:** `applied`, `screening_failed`, `excluded`, `screened`, `shortlisted`, `selected` (unused), `interview_scheduled`, `assessed`.
**Never stored:** the candidate's email address in the feedback row or graph state (read only when sending), raw audio/video, live messages, join tokens (only hashes), JWTs, LiveKit tokens, the PIN (only its hash), the photo taken when joining, camera frames, the original application photo file (only a re-saved JPEG).

### 3.5 UI design
> - The owner wants a **very professional, modern and beautiful UI**.
> - **Before implementing any UI screen or change: share the understanding, show a mockup on the design canvas, wait for approval, then apply it exactly.**
> - Design canvas: https://claude.ai/artifact/1YsLaBugibMF1nbsWtcWYj (all approved mockups; Module 5 boards: `M5LiveTranscript`, `M5TranscriptStates`, `M5TranscriptViewer`, `M5TranscriptViewerStates`; Module 6 boards: `M6Assessments`, `M6AssessmentsStates`, `M6Report`, `M6ReportStates`, `M6PdfA`, `M6PdfB`, `M6CompareSelect`, `M6Compare`; Module 8 (F7) boards: `M8PinEntry`, `M8PinStates`, `M8PreJoinConsent`, `M8Capture`, `M8CaptureStates`, `M8WaitingAllSet`, `M8InterviewsIdentity`, `M8RoomProfile`, `M8IdentityStates`, `M8SidebarPhoto`, `M8NewPin`; Module 7 (F11) boards: `M7ScreeningEmails`, `M7AssessmentsDecisions`, `M7ReportDecision` (the Decision tab), `M7EmailReview`, `M7EmailWarning`, `M7Confirms`, `M7EmailStates`, `M7AssessmentsCompact`, `M7ScreeningRankingV2`, `M7ScreeningEmailsTab`).
> - **No footer note tiles or explanation boxes on any mockup page** (owner); explanations go in the chat.

Theme (FINAL): clean corporate SaaS, white/pale-blue backgrounds, blue primary `#1557E0`, navy headings `#0B1F4B`, body text `#51607A`, rounded cards, subtle shadows; each stage its own colour (no dark navy fills). Tailwind tokens in `frontend/src/index.css` (brand, navy, body, mist, tint, line, success, warning, danger, teal, amber, violet + `-soft`).

**Screens (BUILT):** landing, login, sidebar (Dashboard, Jobs, AI Agent, Knowledge Base; stays in place while the page scrolls on wide screens), Dashboard, Jobs page, job page tabs (Job post, Applications, Screening with sub-tabs Final ranking / Requirement match / **Feedback emails**, Interviews, **Assessments** with a "to review" badge; Screening and Assessments also show "N emails to send"), AI Agent page (cards, job brief), Knowledge Base, interviewer room `/app/interviews/:sessionId/room`, transcript viewer `/app/interviews/:sessionId/transcript`, **assessment page** `/app/interviews/:sessionId/assessment` (Q&A, Coverage, Report and, once approved, **Decision** tabs), **email review panel** (wide side panel with ‹ › between candidates), **compare page** `/app/jobs/:jobId/compare?ids=…`, candidate pages `/interview/:token` (**PIN**, pre-join, **photo step**, waiting, room, ended).
**Job tab ticks (BUILT):** each tab turns green when its step is finished; Interviews when at least one interview is completed and none is scheduled or in progress; Assessments when every completed interview has an approved report. The open tab is always blue.
**Next screens:** F8–F10 (mockups first). Board titles on the canvas: "Module 8 · F7 Candidate identification (for approval)" (approved 20 Oct) and "Module 7 · F11 Candidate Feedback Composer (for approval)" (approved 20–21 Oct).

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

**LangGraph 5: Candidate Feedback** (BUILT, F11, `app/graphs/feedback/`): `load_evidence` → (`draft_feedback` for rejections | `use_template` for Hire and CV not readable | `handle_error`) → `check_fairness` (code) → `review_email` (AI) → `save_draft` → `human_review` (`interrupt`) → approve / send anyway → `send_email` (mcp-google) → `record_sent`, or failed → `mark_not_sent` → `human_review` (Try again); edit → `check_fairness` (warnings only, never rewritten); request changes → `draft_feedback` with the note (3 fresh attempts); discard → end. A problem from either check is sent back for a rewrite up to 3 times (`MAX_ATTEMPTS`), then kept as a warning naming the exact words. AI down on a first draft → `handle_error`; during a rewrite → `revision_failed`, the old draft stays. Thread `feedback-{candidate_id}`, deleted before each new writing run and with the candidate or job.
- **Evidence (`store.load_evidence`):** screening: met requirements (scored) or CV skills (excluded) as strengths, plus the **CV profile** (id `CV`: the CV summary with the name removed by `_without_name`, else the job titles in the CV); growth = preferred requirements not met / partly met, or every exclusion reason (`R…`, `EXP`, other wording `MH…`); interview: the approved report's strengths and weaknesses. No limit on the number of points (each cut to 300 characters, contacts masked).
- **Writing (`writing.py`, FINAL):** free, natural wording; the order is a guide only (greeting `[first name]` → thanks → strengths → apology and reason → level sentence → warm closing). Strengths are a **short summary (1–2 sentences)** led by the candidate's main area, even when it is not the role's focus; left out when there are none. Reason: must-haves "we could not find in your CV"; preferred "extra experience the role also looks for"; interview growth areas; none → "many strong applications". Level sentence by `templates.role_level` (senior from 3 years: "from the very first day"; junior; entry for intern/trainee/apprentice/graduate). Hire and CV-not-readable are fixed messages (Hire names the role; no offer details).
- **Checks (FINAL):** code (`fairness.py`): scores, other candidates, personal topics, promises, offer details, identity check, personal data (emails, phones of 9+ digits, links), quotes of 4+ words, HTML or placeholders, and named skills or tools found in neither the candidate's points nor the job's requirements; words from the job's own requirements are allowed. AI review (`review_email`): respectful, unsupported claims, unfair meaning; when it cannot run the draft gets `not_checked`.
- Greeting name: `templates.first_name` skips prefixes (Md., Mst., Dr., Engr., …) and fixes all-capital names.
- Diagram: `docs/LangGraph_5_Candidate_Feedback_30221_Farhan.pdf` (draw.io source kept by the owner).

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
| `send_email` (mcp-google), called by LangGraph 5 | Backend-only | Yes | BUILT (F11) |
External MCP tools are called only by the backend after approval and are never listed to the LLM.

### 4.4 Google integration
OAuth consent in Testing mode: **the sign-in expires about every 7 days** → run `python -m scripts.google_auth` in `backend/` on the host, then `docker compose restart mcp-blogger mcp-google`. **Renewed 20 Oct 2026; expired again on the office PC on 22 Oct. Renew before the demo on 27 Oct 2026.** Scopes: blogger, forms (read), drive (read), gmail.send, calendar.events. Files in `secrets/` (never on GitHub; copied between PCs by USB). Check scripts: `form_check`, `blogger_check`, `mcp_check`, `google_check`.

### 4.5 API endpoints (BUILT; interviewer role unless marked)
- Public: `GET /health`, `POST /auth/login`. `GET /auth/me`, `GET /ai/status`.
- Chat: `WS /chat`, `GET/DELETE /chat/conversations…`, `GET /chat/{thread_id}`, `POST /chat/messages`, `POST /chat/{thread_id}/approval`, `PUT /chat/{thread_id}/description`.
- Knowledge: `POST/GET /knowledge/documents`, `DELETE /knowledge/documents/{id}`.
- Jobs: `GET /jobs`, `GET/DELETE /jobs/{id}`, `PUT /jobs/{id}/profile`, `POST /jobs/{id}/archive` (no UI), `GET /jobs/{id}/activity`, `POST /jobs/{id}/intake`, `GET /jobs/{id}/intake/status`, `GET /jobs/{id}/candidates`, `POST /jobs/{id}/screen`, `POST/DELETE /jobs/{id}/shortlist`.
- Candidates: `GET /candidates/{id}/cv`, `GET /candidates/{id}/photo` (F7, interviewer only, `photo.jpg`, no-store), `PUT /candidates/{id}/shortlist`, `DELETE /candidates/{id}` (also removes the photo and face code). `CandidateSummary` adds `has_photo`, `face_status`, `face_problem`.
- Interviews: `GET/POST /jobs/{id}/interviews`, `POST /jobs/{id}/interviews/preview`, `GET /interviews/rules`, `GET /interviews/{id}`, `POST /interviews/{id}/room`, `/admit`, `/end`, `GET /interviews/{id}/transcript`, `GET/POST /interviews/{id}/questions`, `PATCH /interviews/{id}/questions/{qid}`, `GET/POST /interviews/{id}/chat`, `PUT /interviews/{id}` (reschedule), `POST /interviews/{id}/cancel`, `POST /interviews/{id}/pin` (F7: new link and PIN), `DELETE /interviews/{id}` (cancelled only). `InterviewSessionSummary` adds `identity` (result, score, other_candidate_name, other_score, reason, checked_at; empty for interviews scheduled before F7).
- Candidate: `POST /join/info`, `/join/pin`, `/join/enter` (no pass); with the pass: `POST /join/identity`, `/join/identity/skip`, `GET /join/status`, `POST /join/leave`, `/join/room`.
- Tasks: `GET /tasks/{id}`. **To remove later:** demo endpoints `/graphs/demo…`, `POST /tasks/demo`.
- Assessments (Module 6): `POST /interviews/{id}/evaluate`, `POST /jobs/{id}/evaluate`, `GET /jobs/{id}/evaluation`, `POST /interviews/{id}/report`, `GET /interviews/{id}/assessment`, `POST /interviews/{id}/assessment/questions`, `POST /interviews/{id}/assessment/review` (approve / request_changes / edit), `GET /interviews/{id}/assessment/report.pdf?tz=` (file `assessment_<job code>_<date>.pdf`), `GET /jobs/{id}/assessments` (ranked list with coverage, also used by the comparison), `POST /jobs/{id}/assessments/approve` (approve all drafts). All interviewer-only (candidates get 403).
- Decisions and feedback emails (F11, interviewer only): `PUT /candidates/{id}/decision` (hire, reject or null), `POST /jobs/{id}/decisions` (by rule: `top` or `min_score`), `GET /jobs/{id}/feedback` (running/last task, emails to send per stage), `POST /jobs/{id}/feedback` (write, background), `POST /jobs/{id}/feedback/send` (send all passed of a stage, background), `GET /candidates/{id}/feedback`, `POST /candidates/{id}/feedback/review` (approve, send_anyway, edit, request_changes, discard). `CandidateSummary`, `RankedAssessment` and `AssessmentOut` add `decision`, `feedback_status` (and `feedback_warnings`).
- **Later:** Re-evaluate in the UI (PENDING).

### 4.6 Error handling and logging
JSON logs (IDs and numbers only: no names, emails, CV text, transcript text, tokens, keys or prompts). Worker events (all with `provider`): `transcription_worker_started` (provider, key set), `interview_audio_joined`, `stt_connected`, `transcript_turn_saved` (speaker, times, word count), `stt_stream_finished` (turns, dropped chunks, skipped messages, delay figures), `stt_refused` (HTTP status), `stt_disconnected` (error type, close code), `stt_error_message`, `stt_message_skipped`, `stt_not_configured`. Evaluation events (ids, counts and labels only): `qa_segmentation_empty`, `qa_references_found`, `qa_references_unavailable`, `qa_evaluation_invalid` (attempt, problem labels such as `quote_not_found`, `accuracy_missing`), `qa_evaluation_kept`, `assessment_report_untraced`, `assessment_claims_dropped`, `assessment_reviewed`, `assessments_approved`, `report_written`, `report_pdf_built`, `evaluation_finished`. F7 events (ids, labels and scores only): `face_enrolled`, `face_photo_unusable` (problem code), `face_check_failed`, `interview_pin_wrong`, `interview_pin_locked`, `interview_pin_renewed`, `identity_photo_unusable`, `identity_checked` (result, score). F11 events (ids, kinds, counts and warning codes only, never email text): `decision_set`, `decisions_applied`, `feedback_fairness_failed`, `feedback_review_failed`, `feedback_drafted`, `feedback_reviewed`, `feedback_send_failed`, `feedback_sent`, `feedback_not_written`, `feedback_writing_finished`, `feedback_sending_finished`. PENDING: simplify the logging code after all other tasks.

### 4.7 Innovation feature: Candidate Feedback Composer (F11, BUILT, Module 7)
After the decision, a personal, fair feedback email for every candidate, written from their own saved job-related evidence, checked by code and by an AI review, and sent through Gmail only after the interviewer approves it.

| Who | Decision | Email kind | First draft |
|---|---|---|---|
| Not shortlisted after screening (`screened`, `excluded`) | Rejected automatically | `screening_reject` | AI |
| CV could not be read (`screening_failed`) | Rejected automatically | `cv_unreadable` | Fixed message |
| Interviewed, report approved, **Reject** | Interviewer | `interview_reject` | AI |
| Interviewed, report approved, **Hire** | Interviewer | `hire` | Fixed message |

- **Privacy (FINAL):** the AI never gets the candidate's name (writes `[first name]`; the name is also removed from the CV summary), email address, scores, other candidates, transcript quotes, the identity check or the interviewer's note. The address is read only when sending. Sent text, approver and time are kept with the candidate and deleted with the candidate or job.
- Docs: README section "Innovation Feature: Candidate Feedback Composer (F11)", `docs/feedback_composer_design.md`, `docs/innovation_rationale.md` (draft written by Claude at the owner's request; the owner reviews it), LangGraph 5 diagram. Owner's backend explainer: `HireLucent_F11_Backend_Story_30221_Farhan.pdf` (not in the repo).

---

## 5. Development status (22 Oct 2026)

### 5.1 Redmine tree and status
- **Module 2** Foundation: BUILT, merged into `dev`.
- **Module 3** (Story #647080, F1 + F2): BUILT, merged into `dev`.
- **Module 4** (Story #648326, F3): BUILT, merged into `dev` (14 Oct).
- **Module 5** (Story #648345, F4): BUILT, merged into `dev`.
  - Features 22–27 complete (#648346, #648347, #648349, #648354, #648355, #648357); AssemblyAI provider `Refs #648360`.
- **Module 6** (F5 + F6), branch `module/6-assessment`: BUILT, merged into `dev` (PR #5, `59b344d`). Story and feature ids: (fill in from the Redmine tree).
  - Q&A segmentation #650073 (+ #650074 multi-part and small talk) · Response evaluation #650075 · reference-based accuracy #650076 · justification with evidence #650077 · requirement coverage #650078 · Q&A screens #650079 · consolidated assessment #650080 (scores and label) and #650081 (strengths, weaknesses, gaps, areas, traceability) · report view #650082 · export and print #650083 · candidate comparison #650084 (also ranked list and Assessments tab).
  - pgAdmin (extra tool): `Refs #646551`. Fixes from the full test: `Refs #650075, #650076, #650080, #650081, #650084`.
- **Module 8 Stretch 1** (F7), branch `module/8-stretch-1-candidate-identification`, Redmine task **#650400**: BUILT, full test passed by the owner (20 Oct); commits `d7d679a`, `7d8b58e`, `fa6f5f5`, `9929dbe`, `5c2cf47`, `b701750`, `9bab217`, `d11e356` + docs commit (`Closes #650400`); **merged into `dev` (PR #6, `2bcc1e2`)**. Follow-up fix on `module/7-innovation`: `567d058` "Send only the face area of the photo" (`Refs #650400`).
- **Module 7** (F11 Innovation), branch `module/7-innovation`, Story **#650131**: BUILT, tested by the owner (22 Oct); next: PR into `dev`. Redmine task, feature and module descriptions and the daily notes (20/10 and 21/10) given.
  - Feature 28 Concept & Rationale #650133: tasks #650166 (finalise concept; assigned to Jishnu Sardar), #650169 (rationale).
  - Feature 29 Feature Design #650135: tasks #650161 (data flow, workflow, API, integration), #650164 (screens, mockups on the design canvas).
  - Feature 30 Feature Implementation #650138: tasks #650154 (backend and AI workflow), #650157 (screens).
  - Feature 31 Platform Integration #650140: task #650152.
  - Feature 32 Testing & Documentation #650142: tasks #650146 (testing), #650148 (README).

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

### 5.6 Module 8 Stretch 1: F7 Candidate Identification (BUILT, 20 Oct)
Branch `module/8-stretch-1-candidate-identification` (from `dev`), Redmine task #650400. Delivered as one zip (`hirelucent_step_8.2`) after all mockups were approved; 8.1 was the face-match test script.
- **Decisions (FINAL, 20 Oct):** trainer approved going beyond clarification #21 · photo and consent both **required** in the form (consent option A: one checkbox) · **the application photo is kept** (owner's change from "face code only") so the interviewer can compare it with the video · no photo from inside the CV · face data deleted when the candidate or the job is deleted (no separate retention period) · photo taken automatically after **5 s of green** plus a **Take photo** button · 3 photo tries, then continue · one consent box at pre-join covering transcript and photo · match score and the other applicant's name shown to the interviewer · "Send a new PIN" also renews the link · one migration `0015` · bands verified ≥ 0.50 / low ≥ 0.363 / very low below (from the owner's face test) · sidebar kept as built: only the Identity check row changes, plus the application photo and an **Areas to probe** section.
- **Built:** see Step 5 (enrolment), Step 7 (PIN in the invitation, New PIN), Step 8 (PIN page, photo step, identity check), Step 9 (room sidebar), §3.1, §3.4, §4.5, §4.6. README section "Candidate identification and biometric data" (what is stored, where, who sees it, how long, limits).
- **Files:** backend `app/services/face_models.py`, `face_service.py`, `pin_service.py`, `identity_service.py`, `scripts/face_match_check.py`, `alembic/versions/0015_add_candidate_identification.py`, `tests/test_identification.py`; frontend `scripts/face-guide-files.mjs`, `lib/faceGuide.js`, `lib/identity.js`, `hooks/useFaceGuide.js`, `hooks/useCandidatePhoto.js`, `components/join/PinEntry.jsx`, `IdentityCapture.jsx`, `components/interviews/IdentityChip.jsx`; changes in intake, google_forms, scheduling, interview_emails, join, job_deletion, CandidateProfile, InterviewList, InterviewsTab, InterviewRoomPage, PreJoin, WaitingRoom.
- **Settings:** `FACE_MODELS_DIR` (default `models`), `MAX_PHOTO_MB` (default 5; the owner's PCs use 10 to match the form).
- **Tests:** 647 backend tests at `d11e356` (45 new); the migration was run up and down on PostgreSQL.

### 5.7 Module 7: F11 Candidate Feedback Composer (BUILT, 22 Oct)
Branch `module/7-innovation` (from `dev`). Delivered as zips `hirelucent_step_7.3` and `_v2`, then one full zip `hirelucent_module_7_f11`, committed by the owner in 11 commits `028a2c8` … `4d9838d`.
- **Decisions (FINAL, 20–21 Oct):** both stages (screening rejections and after the interview) · after the interview **Hire or Reject only, no Hold** · decisions only after the report is approved, by row or by rule · everyone not shortlisted is rejected at screening, shortlist and decision locked once the email is sent · emails are different for every candidate: AI for rejections, fixed messages for Hire and CV not readable, every email editable · warm, inspirational tone, reason worded for the role level · **buttons only** (chatbot sending is future work) · Send anyway after a confirm (option A); Send all passed skips drafts with warnings · decision on a new **Decision** tab so the Report tab stays unchanged · **v2 (21 Oct):** no limits on points and no exact-word checks (free wording); safety checks only in code plus one AI review of tone, unsupported claims and unfair meaning; warnings name and highlight the exact words; the interviewer's edits are checked but never rewritten · strengths: CV profile first, short summary, left out when empty; greeting by the name the candidate goes by.
- **Built:** see Step 6, Step 14, Step 15, §3.1, §3.4, §3.5, §4.1 (LangGraph 5), §4.3, §4.5, §4.6, §4.7.
- **Files:** backend `app/models/feedback.py`, `app/schemas/feedback.py`, `app/graphs/feedback/` (`templates.py`, `store.py`, `writing.py`, `fairness.py`, `graph.py`), `app/services/feedback_service.py`, `app/api/routes/feedback.py`, `alembic/versions/0016_add_candidate_feedback.py`, `tests/test_feedback.py`; changes in enums, candidate, assessment, schemas candidate/assessment, task_service (`FEEDBACK_WRITING`, `FEEDBACK_SENDING`, `NOT_CV_WORK`), intake, screening, evaluation, shortlist, job_deletion, routes/jobs, router. Frontend `lib/feedback.js`, `hooks/useFeedback.js`, `components/feedback/` (EmailChip, EmailButtons, FeedbackEmail, FeedbackPanel, DecisionButtons, DecisionRuleBar, DecisionTab, ScreeningFeedback); changes in SidePanel (`isWide`), FinalRanking, MatchRanking, candidates, CvFacts, JobTabs, JobPage, ScreeningTab, AssessmentsTab, AssessmentPage, RankedList, `lib/results.js`.
- **Tests:** 737 backend tests at `567d058` (1 skipped in the container); frontend lint and build clean; screens checked at 1280 px and wide widths.

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
10. Transcription "later" ideas (not required): store per-turn confidence (next free migration `0017`), keyterm spelling table (FastAPI, Kubernetes…), endpointing / turn length as settings.
11. Google STT as a third provider (PENDING).
12. **Question inferred from the candidate's answer** when the interviewer's question is lost from the transcript (owner: "keep reminding, I will tell you later"). Today such an answer is skipped.
13. **Re-evaluate** option for interviews that already have a report (offered; the API allows it, the UI does not). Workaround: `POST /interviews/{id}/evaluate` from `/docs`.
14. **Candidates who never attend their interview (F11):** no report can be approved, so they cannot be decided and get no email. Option: a "Did not attend" decision with its own email (PENDING, owner decides).
15. **Liveness check (F7)**: blink, or "turn your head left / right", against a printed photo held up to the camera. Owner: later.
16. **Face status on the Applications or Screening tab** (e.g. "photo not usable (too blurry)") before scheduling. Owner: "I will tell you later".
17. Building on an 8 GB PC: build images one at a time (`docker compose down` → `build backend` → `build frontend` → `up -d`); a full `up -d --build` crashed WSL once (Docker has ~3.4 GB).
18. **Starting feedback emails from the AI Agent chat (F11 future work):** an approval card in the conversation and a read-only email status tool.
19. **Office network blocks Docker Hub** (`auth.docker.io`): use the registry mirror `"registry-mirrors": ["https://mirror.gcr.io"]` in Docker Desktop → Docker Engine, or download images over a phone hotspot once.

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
- **F11:** the AI follows the writing guidance (short strengths, free wording) almost always but not every time; the interviewer reviews every draft before sending. Candidates who never attend their interview get no email (deferred item 14). If the AI review cannot run, the draft is marked "not checked".
- **F7:** no liveness check yet (a clear printed photo could pass; the interviewer still sees the video and the label is advice only); twins and close look-alikes can match; an old or poor application photo lowers the score (the photo's age cannot be checked; the form asks for under 3 months); interviews scheduled before F7 have no PIN and no check; the browser face model is downloaded at the frontend build (without it the photo step has no live tips and only the server check runs).

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
- **Tests:** `cd backend && source .venv/Scripts/activate && python -m pytest -q && cd ..` (737 tests at `567d058`; on the Windows venv a few are skipped (Tesseract, `livekit`); the first run on Windows takes 1–2 minutes, do not interrupt it). Frontend: `npm run lint`, `npm run build`. Use forward slashes in Git Bash paths.
- **pgAdmin (optional):** `docker compose --profile tools up -d pgadmin` → http://localhost:5050 (or http://127.0.0.1:5050); needs `PGADMIN_EMAIL` / `PGADMIN_PASSWORD` in that PC's `.env`. It is not started by `docker compose up -d` (tools profile); `COMPOSE_PROFILES=tools` in a PC's own `.env` starts it automatically there. After a Docker/WSL crash, recreate it (`--force-recreate pgadmin`) or restart Docker Desktop if the page is empty.
- **Commits:** `<type>(<scope>): <Summary>` (≤50 chars, imperative), body bullets "- " wrapped at 72, footer `Refs #id` or `Closes #id`; multiline `git commit -m … -m …`, then `git push origin <branch>`. **Claude never commits or pushes; the owner does.**
- **Redmine:** Textile. Daily notes `h1. *Date: dd/mm/yy*` + past-tense bullets, only work actually done; descriptions = one paragraph + `*Outcomes:*` bullets.
- **DB check shortcut (Git Bash):** `hdb() { docker compose exec -T postgres sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"' <<< "$1"; }`
- **Security:** never commit `.env` or `secrets/`; never paste keys in chat; no personal data in repo or logs; external actions only after HITL.
