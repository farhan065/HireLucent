# HireLucent handoff (update this every time you switch accounts)

**Last updated:** 19 Oct 2026, 14:00 (Dhaka) · **by:** the account that finished Module 6 · **PC:** office

## Git state
- Branch: `module/6-assessment` (exists on both PCs; on a new PC: `git fetch origin` then `git checkout -b module/6-assessment origin/module/6-assessment`)
- Last code commit: `0bee242` feat(jobs): Tick the Interviews and Assessments tabs (this docs update comes after it)
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
- Nothing half-built. Module 6 is complete.

## Next step
1. Commit this docs update, then open the pull request `module/6-assessment` → `dev` (Claude writes the PR description; the owner merges).
2. Redmine: feature descriptions for the finished Module 6 features and the Module 6 description (needs the Module 6 tree screenshot with story and feature ids).
3. Create `module/7-…` from `dev` and start Module 7 (innovation: Candidate Feedback Composer, and the Hire / Hold / Reject decision): understanding and questions first, mockups before any UI.

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
