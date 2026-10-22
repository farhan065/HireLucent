# HireLucent handoff (update this every time you switch accounts)

**Last updated:** 22 Oct 2026, 14:40 (Dhaka) · **by:** the account that built F11 · **PC:** office

## Git state
- Branch `module/7-innovation`: Module 7 (F11, Candidate Feedback Composer) complete. F11 commits `028a2c8` … `4d9838d`, then the F7 fix `567d058` ("Send only the face area of the photo", `Refs #650400`), then this docs commit.
- Module 8 Stretch 1 (F7) is merged into `dev` (PR #6).
- Next: **pull request `module/7-innovation` → `dev`**, then create the next stretch branch from `dev` (`module/8-stretch-<n>-<feature>`).
- Uncommitted work: none
- Tests: 737 backend tests (1 skipped in the container; a few more on the Windows venv: Tesseract, `livekit`); frontend lint and build clean

## Done in the last sessions (20–22 Oct)
- **F11 Candidate Feedback Composer** (Module 7, Story #650131), tested by the owner:
  - Screening: everyone not shortlisted is rejected; **Feedback emails** sub-tab; Status and Feedback email columns in the Final ranking; shortlist locked once the rejection email is sent
  - Assessments: Hire or Reject (no Hold) after the report is approved, per row or **Decide by rule**; 8-column list with summary cards; **Decision** tab on the assessment page
  - LangGraph 5 writes each email (AI for rejections, fixed messages for Hire and CV not readable), checks it in code and with an AI review, rewrites up to 3 times, keeps warnings naming the exact words, waits for the interviewer, sends through mcp-google `send_email`
  - Strengths: CV profile first (name removed), short summary, left out when empty; greeting by the name the candidate goes by
  - Migration `0016` (`candidate_feedback`); 7 new endpoints; README section, design doc, LangGraph 5 diagram, rationale draft
- Redmine: all Module 7 task descriptions and daily notes (20/10, 21/10), the five feature descriptions and the module description given and posted by the owner
- Backend explainer PDF for the owner: `HireLucent_F11_Backend_Story_30221_Farhan.pdf` (not in the repo)
- Office PC moved to `module/7-innovation` (22 Oct)

## In progress
- Nothing half-built.

## Next step
1. Open the PR `module/7-innovation` → `dev` and merge it.
2. **New chat: the remaining stretch features F8–F10**, each on its own branch from `dev`. Ask for the Redmine ids first.

## Decisions made for F11 (already in project_context.md §5.7)
- Both stages; Hire or Reject only; decisions only after approval; locked once the email is sent.
- Free wording, safety checks only (code) plus one AI review of meaning; no point limits.
- Buttons only; chatbot sending is future work.
- Send anyway after a confirm; Send all passed skips drafts with warnings.

## Reminders
- **Keep reminding (owner's request):** the question inferred from the candidate's answer when the interviewer's question is lost from the transcript (deferred item 12). Not built.
- **PENDING (owner decides):** candidates who never attend their interview get no feedback email (deferred item 14).
- The owner reviews `docs/innovation_rationale.md` and tells Claude if anything should change.
- Re-evaluate in the UI is not built (deferred item 13); workaround `POST /interviews/{id}/evaluate` from http://localhost:8000/docs.
- **Google sign-in expired on the office PC on 22 Oct.** Renew before the demo on 27 Oct: `python -m scripts.google_auth` in `backend/`, then `docker compose restart backend mcp-google mcp-blogger`. The office PC needs the `secrets/` folder (copy by USB, never by chat or GitHub).
- **Office network blocks Docker Hub:** add `"registry-mirrors": ["https://mirror.gcr.io"]` in Docker Desktop → Settings → Docker Engine, or download the images once over a phone hotspot.
- **Google Form:** extra questions must not have "name", "email", "photo" or "consent" in their titles, and must not be file uploads (HireLucent finds its questions by these words and takes the first non-photo upload as the CV).
- **8 GB PC:** build one image at a time: `docker compose down` → `docker compose build backend` → `docker compose build frontend` → `docker compose up -d`. A full `up -d --build` crashed WSL once.
- pgAdmin is not started by `up -d` (tools profile): `docker compose --profile tools up -d pgadmin`, then http://127.0.0.1:5050.
- Each PC's `.env` needs `DEEPGRAM_API_KEY`, `ASSEMBLYAI_API_KEY` (optional), `STT_PROVIDER`, `STT_KEYTERMS` and, for AssemblyAI, `ASSEMBLYAI_URL=wss://streaming.assemblyai.com/v3/ws`; for pgAdmin `PGADMIN_EMAIL` and `PGADMIN_PASSWORD`; for F7 `MAX_PHOTO_MB=10` to match the form's 10 MB photo limit (copy by USB, never by chat or GitHub).
- Check the running speech-to-text provider: `docker compose logs transcription-worker | grep transcription_worker_started | tail -1`.
- Keep `face_test/` (owner's photos) local only; it is git-ignored. Delete the photos when no longer needed for demos.
- Each PC has its own database: Knowledge Base files, applications and interviews must be added again on the other PC.
