# HireLucent handoff (update this every time you switch accounts)

**Last updated:** 20 Oct 2026, 10:15 (Dhaka) · **by:** the account that finished Module 6 · **PC:** office

## Git state
- Module 6 merged into `dev` (PR #5, `59b344d`).
- New branch: `module/8-stretch-1-candidate-identification` from `dev`; its first commit is this docs update (the F7 plan).
- Uncommitted work: none
- Tests: 602 backend tests (a few skipped on the Windows venv: Tesseract, `livekit`); frontend lint and build clean

## Done in the last sessions
- Steps 6.1–6.10: LangGraph 3 (Q&A Analysis), LangGraph 4 (Final Assessment with HITL review), Evaluate / Evaluate all, assessment page (Q&A, Coverage, Report), Assessments tab with ranking, Approve all drafts, report PDF with Print / Download, compare up to 3 candidates
- Extra: optional pgAdmin viewer (tools profile, localhost:5050) (`Refs #646551`)
- 6.11 full test by the owner, all passed, with four fixes:
  - evaluation keeps working on messy, real conversations (not answered, pauses, speech-to-text spelling, last-attempt keep, Knowledge Base down)
  - report quotes traced with the same tolerance
  - each finding listed once, neutral "double-check before deciding" wording
  - green ticks on the Interviews and Assessments tabs
- LangGraph 3 and 4 diagrams redrawn to match the code (PDFs in `docs/`, draw.io sources with the owner)
- Study guides: "Module 6 Study Guide" and "Module 6 Backend Study Guide" (Claude docs)
- Redmine daily notes given for #646551, #650075, #650076, #650081, #650084

## In progress
- Nothing half-built. Module 6 is complete and merged. The F7 plan is agreed but not built (project_context §5.6).

## Next step
1. Redmine: feature descriptions for the finished Module 6 features (Module 6 description already given; needs the tree screenshot for feature ids).
2. **Module 8 Stretch 1, F7 Candidate Identification** (plan: project_context §5.6; start text: pasted into the new chat by the owner):
   - settle the open questions (capture button vs auto, blink check, retention, CV photo fallback)
   - step 1: face-match test script with the owner's passport photo and webcam
   - mockups (PIN entry, oval capture, identity labels, profile panel) before any UI
3. Then Module 7 (innovation: Candidate Feedback Composer, and the Hire / Hold / Reject decision), then the other stretch features (`module/8-stretch-<n>-<feature>`).

## Decisions made in Module 6 (already in project_context.md)
- Evaluate on request, one at a time, in the background with progress.
- Overall = 0.4 × CV + 0.6 × interview; label strong fit ≥ 70, possible fit ≥ 60, otherwise not a fit (decision support only).
- Accuracy from Knowledge Base `reference` documents first; technical answers otherwise judged by the AI; company answers otherwise not checked.
- Report review: approve / request changes / edit (no adding points) + Approve all drafts, all with confirms.
- PDF export (no candidate name in the file name), comparison of up to 3 candidates.
- Evaluation keeps what can be trusted instead of failing; each finding appears once.
- pgAdmin optional (tools profile). Way 2 handled manually with Cloudflare quick tunnels (no code).

## Reminders
- **Keep reminding (owner's request):** the question inferred from the candidate's answer when the interviewer's question is lost from the transcript (deferred item 12). Not built.
- Re-evaluate in the UI is not built (deferred item 13); workaround `POST /interviews/{id}/evaluate` from http://localhost:8000/docs.
- Google sign-in renewal was due ~19 Oct 2026 (`python -m scripts.google_auth` in `backend/`, then `docker compose restart mcp-blogger mcp-google`).
- Each PC's `.env` needs `DEEPGRAM_API_KEY`, `ASSEMBLYAI_API_KEY` (optional), `STT_PROVIDER`, `STT_KEYTERMS` and, for AssemblyAI, `ASSEMBLYAI_URL=wss://streaming.assemblyai.com/v3/ws`; for pgAdmin `PGADMIN_EMAIL` and `PGADMIN_PASSWORD` (copy by USB, never by chat or GitHub).
- Each PC has its own database: Knowledge Base files (for example `ml_reference_notes.txt`) and interviews must be added again on the other PC.
- Check the running speech-to-text provider: `docker compose logs transcription-worker | grep transcription_worker_started | tail -1`.
