# HireLucent handoff (update this every time you switch accounts)

**Last updated:** 23 Oct 2026, 01:45 (Dhaka) · **by:** the account that built F8 · **PC:** DESKTOP-8KPB4FM

## Git state
- Branch `module/8-stretch-2-cv-claim-verification`: Module 8 Stretch 2 (F8, CV Claim Verification) complete. Commits `ea82956` (migration and column), `3e06ab0` (LangGraph 4 claim nodes), `96fb556` (endpoints), `b3a66bb` (PDF section C), `5b49dcb` (CV claims tab), `3ad4d71` (README and diagram, `Closes #650678`), then this docs commit.
- Module 7 (F11) is merged into `dev` (PR #7, `63ac3ec`); F7 is merged (PR #6).
- Next: **pull request `module/8-stretch-2-cv-claim-verification` → `dev`** (text given in the chat), then create the next stretch branch from `dev`.
- Uncommitted work: none
- Tests: 778 backend tests (1 skipped); frontend lint and build clean

## Done in the last session (22–23 Oct)
- **F8 CV Claim Verification** (Module 8, Feature 41 #650674, task #650678):
  - Every CV claim (total years, each job, project, certification, education entry, skill) compared with the interview: contradiction, unverified, not discussed or consistent; points to check before deciding, never accusations; never change scores, the report or the decision; never in F11 emails
  - LangGraph 4: `extract_claims` → `judge_claims` (AI) → `check_claims` (code, up to 3 attempts) → `save_claims`, before the report; claims-only run on thread `cv-claims-{id}` for **Check CV claims** (old interviews) and **Check again** (AI was down)
  - Migration `0017` (`assessments.claim_checks`); 2 new endpoints; CV claims tab after Requirement coverage; Checked / Dismissed with a note; warning when approving with an open contradiction (also in Approve all drafts); progress step "Checking CV claims"; PDF section C; README section; LangGraph 4 diagram redrawn
- Mockups on the design canvas: `M8ClaimsTab`, `M8ClaimsStates`, `M8ClaimsPdf` (approved 23 Oct; owner may ask for changes later)
- Redmine: task #650678 description and daily note (dated 22/10/26, owner to confirm), Feature 41 description given
- The editable `LangGraph_4_Final_Assessment_Farhan_30221.drawio` was given to the owner (not in the repo)
- `project_context.md` updated (§5.8 and the sections it lists)

## In progress
- Nothing half-built. The owner still runs the F8 test checklist (Check CV claims on an old interview, Checked/Dismissed, Evaluate again progress, approval warning, PDF section C, logs).

## Next step
1. Merge the PR `module/8-stretch-2-cv-claim-verification` → `dev`, then `git checkout dev && git pull origin dev` (close the LangGraph 4 PDF in VS Code first: Windows locks open files and the checkout stops).
2. **New chat: F9 Comprehensive Candidate Interview Scoring**, branch `module/8-stretch-3-interview-scoring` from `dev`. Claude can write `claude/starting_context_module_8_stretch_3.md` first. Ask for the Redmine ids.
3. Then F10, Module 9 (integration, testing, README, architecture diagrams), Module 10 (submission), before the demo on 27 Oct.

## Decisions made for F8 (in project_context.md §5.8)
- Every claim; inside Evaluate; nodes in LangGraph 4; tab + PDF only; not in areas to verify.
- Checked / Dismissed with an optional note; approval warns, never blocks.
- No follow-up line, no count tiles; interview box shows the question asked; not-discussed claims as closed chips.
- One-time Check CV claims for old interviews; Check again when only the claim step failed.

## Reminders
- **Keep reminding (owner's request):** the question inferred from the candidate's answer when the interviewer's question is lost from the transcript (deferred item 12). Not built.
- **PENDING (owner decides):** candidates who never attend their interview get no feedback email (deferred item 14).
- The owner reviews `docs/innovation_rationale.md` and tells Claude if anything should change.
- **Google sign-in expired on the office PC on 22 Oct.** Renew before the demo on 27 Oct: `python -m scripts.google_auth` in `backend/`, then `docker compose restart backend mcp-google mcp-blogger`. The office PC needs the `secrets/` folder (copy by USB, never by chat or GitHub).
- **Windows locks open files:** close a PDF or file open in VS Code before `cp -r` from a zip or `git checkout` of another branch ("Device or resource busy" / "Unlink … failed").
- **Office network blocks Docker Hub:** add `"registry-mirrors": ["https://mirror.gcr.io"]` in Docker Desktop → Settings → Docker Engine, or download the images once over a phone hotspot.
- **Google Form:** extra questions must not have "name", "email", "photo" or "consent" in their titles, and must not be file uploads (HireLucent finds its questions by these words and takes the first non-photo upload as the CV).
- **8 GB PC:** build one image at a time: `docker compose down` → `docker compose build backend` → `docker compose build frontend` → `docker compose up -d`. A full `up -d --build` crashed WSL once.
- pgAdmin is not started by `up -d` (tools profile): `docker compose --profile tools up -d pgadmin`, then http://127.0.0.1:5050.
- Each PC's `.env` needs `DEEPGRAM_API_KEY`, `ASSEMBLYAI_API_KEY` (optional), `STT_PROVIDER`, `STT_KEYTERMS` and, for AssemblyAI, `ASSEMBLYAI_URL=wss://streaming.assemblyai.com/v3/ws`; for pgAdmin `PGADMIN_EMAIL` and `PGADMIN_PASSWORD`; for F7 `MAX_PHOTO_MB=10` to match the form's 10 MB photo limit (copy by USB, never by chat or GitHub).
- Check the running speech-to-text provider: `docker compose logs transcription-worker | grep transcription_worker_started | tail -1`.
- Keep `face_test/` (owner's photos) local only; it is git-ignored. Delete the photos when no longer needed for demos.
- Each PC has its own database: Knowledge Base files, applications and interviews must be added again on the other PC.
