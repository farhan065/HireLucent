# Start prompt for a new HireLucent chat (paste everything below the line)

---

I'm Shahriar Farhan, building **HireLucent** (AI-powered recruitment and interview platform) as my BJIT Academy AI Trainee final project, solo, due 27 Oct 2026. I'm continuing development from another Claude chat. The attached/project file **`project_context.md`** is the source of truth for every decision, the architecture and the progress; read it fully before answering. **`HANDOFF.md`** says exactly where I stopped.

## Where I stopped
- Branch **`module/5-transcription`**, last pushed commit **`ba37bd4`** ("feat(room): Add the live transcript panel"). 401 backend tests pass.
- Module 5 steps **5.0 to 5.5 are BUILT and pushed** (Deepgram streaming per speaker, transcript saved per turn, `GET /interviews/{id}/transcript`, live push to the interviewer over LiveKit, live transcript panel with Paused / Not available states). Redmine tasks #648360, #648362, #648363, #648365, #648367, #648369, #648372, #648374 are closed.
- **Next: step 5.6, the transcript viewer for completed interviews (Redmine #648375, Feature 26 #648355).** Then 5.7 robustness (#648376), then close Module 5 and merge into `dev`.

## Step 5.6: what was already proposed (not built yet)
- Interviews tab → each **Completed** interview gets **View transcript** → opens the viewer.
- Viewer: header (candidate, job, date, length); search with highlighted matches, next/previous and "3 of 12"; timestamp navigation (timeline with minute markers, clickable times); turns in the same one-row-per-turn style as the live panel (`frontend/src/components/room/LiveTranscript.jsx`); read-only, interviewer only; reuses `GET /interviews/{id}/transcript`.
- Two questions are still open and must be asked first: (1) **full page** (recommended) or side panel? (2) **Download (.txt)** button or not?
- A **mockup must be shown and approved before building.** The design canvas from my other account is: https://claude.ai/artifact/1YsLaBugibMF1nbsWtcWYj (if you can't open it, ask me for screenshots or make the mockup as a new artifact in this account, matching the theme in `project_context.md` §3.5).

## How you must work with me (same as before, do not change)
1. **Before any step:** briefly share your understanding and questions. For any UI, show a mockup first and wait for my approval. Apply approved UI exactly.
2. **Build only after I confirm.** Match the existing code exactly (structure, naming, patterns, comment style, simple code). Read the relevant files in the repo before changing them. Never rewrite working code that the step doesn't need; never repeat completed work.
3. **Deliver each step as `hirelucent_step_X.zip`** containing only the changed files at their repo paths (a corrected re-send gets a new name like `_v2`), plus:
   - apply commands (always starting with `rm -rf` of the old folder):
     ```
     rm -rf ~/Downloads/hirelucent_step_X
     unzip -o ~/Downloads/hirelucent_step_X.zip -d ~/Downloads
     cp -r ~/Downloads/hirelucent_step_X/. .
     docker compose up -d --build
     ```
   - a test checklist ending with "Done when";
   - small commits in my format, then the push command.
4. **Commit format:** `<type>(<scope>): <Summary>` (types feat/fix/docs/style/refactor/test/chore; capitalized, imperative, ≤50 chars); body bullets starting with "- ", wrapped at 72, blank line between; footer `Refs #<id>` (task continues) or `Closes #<id>` (last commit of the task); give it as multiline `git commit -m "…" -m "…"` for Git Bash; then `git push origin module/5-transcription`. **You never commit or push; I do.**
5. **After I push:** check GitHub against what you delivered, then give the **Redmine notes** (Textile: `h1. *Date: dd/mm/yy*` + past-tense bullets of work actually done) and, when asked, task/feature descriptions (one 3–4 line paragraph + `*Outcomes:*` bullets).
6. **Explanations:** I often ask "what does X do / how does it flow". Answer simply with file names, function names and the order of calls. Use names, not pronouns.
7. **Security (strict):** never commit `.env` or `secrets/`; never ask me to paste keys in chat; no personal data in the repo or logs; candidate emails/phones/links never reach the LLM; external actions only after HITL approval; transcript text never logged; raw audio/video never stored.
8. **Tests:** `cd backend && source .venv/Scripts/activate && python -m pytest -q && cd ..` must pass (currently 401). Frontend: `npm run lint` and `npm run build` in `frontend/`.
9. If something in this prompt, `HANDOFF.md`, `project_context.md` or the code disagree, **tell me and ask** which is right (the code wins for names).

## My setup
- Two PCs (home and office), Windows, Git Bash, VS Code, Docker Desktop. Repo: https://github.com/Farhan-014/HireLucent (branch `module/5-transcription`; `dev` has Modules 2–4).
- `.env` holds the keys (Gemini, LiveKit, Deepgram, `STT_PROVIDER=deepgram`, `STT_KEYTERMS=true`; while testing `INTERVIEW_MIN_NOTICE_MINUTES=1`, `JOIN_OPENS_MINUTES_BEFORE=60`). `secrets/` holds the Google sign-in files (copied by USB).
- **Google sign-in renewal due around 19 Oct 2026:** `python -m scripts.google_auth` in `backend/`, then `docker compose restart mcp-blogger mcp-google`.
- DB check shortcut: `hdb() { docker compose exec -T postgres sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"' <<< "$1"; }`

Please confirm you've read `project_context.md` and `HANDOFF.md`, summarise in 5 lines where we are, then ask me the two open questions for step 5.6.
