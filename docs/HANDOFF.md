# HireLucent handoff (update this every time you switch accounts)

**Last updated:** 20 Oct 2026, 20:40 (Dhaka) · **by:** the account that built F7 · **PC:** home

## Git state
- Branch `module/8-stretch-1-candidate-identification`: F7 complete. Last code commit `d11e356`, then this docs commit (`Closes #650400`).
- Next: **pull request `module/8-stretch-1-candidate-identification` → `dev`**, then create the Module 7 branch from `dev` (e.g. `module/7-innovation`).
- Uncommitted work: none
- Tests: 647 backend tests (a few skipped on the Windows venv: Tesseract, `livekit`); frontend lint and build clean

## Done in the last session (20 Oct)
- **F7 Candidate Identification** (Module 8 Stretch 1, Redmine #650400), full test passed by the owner:
  - Google Form needs a required photo upload ("photo" in the title) and a required consent checkbox ("consent" in the title); publishing and `form_check` check both
  - Fetch CVs: application photo checked, re-saved, face code made (OpenCV YuNet + SFace, local); photo kept for interviewers only; deleted with the candidate or job
  - 8-digit interview PIN under the join link (Argon2 hash only), 5 wrong tries lock 15 min, New PIN sends a new link and PIN
  - Candidate: PIN page → pre-join (consent incl. photo) → "Confirm it's you" photo step (MediaPipe oval, tips, 5 s auto photo / Take photo, 3 tries) → waiting room
  - Interviewer: identity chip in the waiting row and Admit bar; room sidebar with the application photo, the Identity check row and Areas to probe
  - README section "Candidate identification and biometric data"; migration `0015`
- Face-match test with the owner's photos: same person 0.58–0.63, other 0.30 → bands 0.50 / 0.363
- Redmine: task #650400 description and daily note, F7 feature description given

## In progress
- Nothing half-built.

## Next step
1. Open the PR into `dev` and merge it.
2. **New chat: Module 7 Innovation, Candidate Feedback Composer (F11)**. Start text: `claude/starting_context_module_7.md` in the Project files. Ask for the Module 7 Redmine ids first.
3. After Module 7, in another new chat: stretch features F8–F10, each on `module/8-stretch-<n>-<feature>` from `dev`.

## Decisions made for F7 (already in project_context.md §5.6)
- Trainer approved face verification beyond clarification #21.
- Application photo kept (not only the face code); face data deleted with the candidate or job.
- Photo and consent required in the form; one consent box at pre-join.
- Never blocks: every candidate with the PIN can join; the result is interviewer-only.
- Liveness check and face status on the Applications tab: later.

## Reminders
- **Keep reminding (owner's request):** the question inferred from the candidate's answer when the interviewer's question is lost from the transcript (deferred item 12). Not built.
- Re-evaluate in the UI is not built (deferred item 13); workaround `POST /interviews/{id}/evaluate` from http://localhost:8000/docs.
- Google sign-in renewed 20 Oct; renew again before the demo (`python -m scripts.google_auth` in `backend/`, then `docker compose restart mcp-blogger mcp-google`).
- **8 GB PC:** build one image at a time: `docker compose down` → `docker compose build backend` → `docker compose build frontend` → `docker compose up -d`. A full `up -d --build` crashed WSL once.
- pgAdmin is not started by `up -d` (tools profile): `docker compose --profile tools up -d pgadmin`, then http://127.0.0.1:5050.
- Each PC's `.env` needs `DEEPGRAM_API_KEY`, `ASSEMBLYAI_API_KEY` (optional), `STT_PROVIDER`, `STT_KEYTERMS` and, for AssemblyAI, `ASSEMBLYAI_URL=wss://streaming.assemblyai.com/v3/ws`; for pgAdmin `PGADMIN_EMAIL` and `PGADMIN_PASSWORD`; for F7 `MAX_PHOTO_MB=10` to match the form's 10 MB photo limit (copy by USB, never by chat or GitHub).
- Check the running speech-to-text provider: `docker compose logs transcription-worker | grep transcription_worker_started | tail -1`.
- Keep `face_test/` (owner's photos) local only; it is git-ignored. Delete the photos when no longer needed for demos.
- Each PC has its own database: Knowledge Base files and interviews must be added again on the other PC.
