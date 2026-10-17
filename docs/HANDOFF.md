# HireLucent handoff (update this every time you switch accounts)

**Last updated:** 17 Oct 2026, 22:30 (Dhaka) · **by:** the account that finished Module 5 · **PC:** (fill in when switching)

## Git state
- Branch: `module/5-transcription`
- Last code commit: `8ebaf13` feat(stt): Add AssemblyAI as a second provider (this docs update comes after it)
- Uncommitted work: none
- Tests: 419 backend tests (on the Windows venv 7 are skipped: 5 need Tesseract, 2 need `livekit`)

## Done in the last session
- 5.6 transcript viewer: full page from View transcript on Completed rows, search with "3 of 12", timeline, Download .txt (closes #648375; Feature 26 complete)
- 5.7 robustness: unreadable/error messages skipped without dropping the connection, delay measured, reconnect waits capped at 5 s (closes #648376; Feature 27 complete)
- 5.8 AssemblyAI as a second, switchable provider with shared `stt_stream.py` (Refs #648360)
- Full Module 5 test done by the owner
- Redmine notes and descriptions given for #648375, #648376, #648360 (follow-up note), Feature 26, Feature 27 and Module 5

## In progress
- Nothing half-built. Module 5 is complete.

## Next step
1. Commit this docs update, then open the pull request `module/5-transcription` → `dev` (Claude writes the PR description; the owner merges).
2. Create `module/6-…` from `dev` and start Module 6 (F5 Q&A Analysis, F6 Final Assessment): understanding and questions first, mockups before any UI.
3. After Module 6: same-Wi-Fi / hotspot demo mode ("Way 2", see project_context §5.4 item 9).

## Decisions made in the last session (already in project_context.md)
- Transcript viewer: full page, Download .txt, text only (no audio is stored, so no playback).
- Robustness scope limited to bad messages + delay measurement (+ 5 s retry cap).
- STT providers: Deepgram (default) or AssemblyAI via `STT_PROVIDER`; switch with `docker compose up -d --force-recreate transcription-worker`. AssemblyAI uses the global address (its EU data zone sent no text). The README reports AssemblyAI's delay: 0.08–0.09 s average, under 0.9 s for the slowest 5%.
- AssemblyAI free plan cannot opt out of model training: test interviews only.
- Render/Vercel, Oracle VM, LiveKit Cloud and router port forwarding are not used.
- Redmine: task description with each daily note; feature/module descriptions when complete; work without its own task uses the closest existing task (`Refs`).
- Docs are updated only at the end of a module or when the owner asks.

## Reminders
- Google sign-in renewal due ~19 Oct 2026 (`python -m scripts.google_auth` in `backend/`, then `docker compose restart mcp-blogger mcp-google`).
- Each PC's `.env` needs `DEEPGRAM_API_KEY`, `ASSEMBLYAI_API_KEY` (optional), `STT_PROVIDER`, `STT_KEYTERMS` and, for AssemblyAI, `ASSEMBLYAI_URL=wss://streaming.assemblyai.com/v3/ws` (copy by USB, never by chat or GitHub).
