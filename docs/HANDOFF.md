# HireLucent handoff (update this every time you switch accounts)

**Last updated:** 16 Oct 2026, 14:40 (Dhaka) · **by:** Account 1 · **PC:** office

## Git state
- Branch: `module/5-transcription`
- Last pushed commit: `ba37bd4` feat(room): Add the live transcript panel
- Uncommitted work: none
- Tests: 401 backend tests pass

## Done in the last session
- 5.1 + 5.2: Deepgram streaming per speaker, turns saved with times, transcript API (closes #648360, #648363, #648365, #648367, #648369)
- 5.3 + 5.4 + 5.5: live push to the interviewer, live transcript panel (one row per turn, newest at the bottom, Jump to latest), Paused / Not available states (closes #648372, #648374, #648362)
- Redmine notes and descriptions given for all of the above, plus Feature 22, 23, 24 and 25 descriptions

## In progress
- Nothing half-built.

## Next step
- **5.6 transcript viewer (#648375).** Ask the owner: (1) full page or side panel, (2) Download (.txt) or not. Then mockup → approval → build.

## Decisions made in the last session (already in project_context.md)
- Live transcript: newest at the bottom, one row per turn (not grouped), grey interim words, no "unclear" mark for now.
- Live text goes to the interviewer only over LiveKit data; accepted only from the hidden worker (no sender identity).
- Job keywords sent to Deepgram, switchable with `STT_KEYTERMS`.
- Minimum experience stays whole years.
- Transcript quality and speed: review later in 5.7 (test with headphones; one window unmuted at a time).

## Reminders
- Google sign-in renewal due ~19 Oct 2026.
- Home PC `.env` still needs `DEEPGRAM_API_KEY`, `STT_PROVIDER=deepgram`, `STT_KEYTERMS=true` (copy by USB).
