# HEARTBEAT.md

Continuity mode is active.

On each heartbeat:
1. Read `NOW.md`.
2. Ensure `memory/YYYY-MM-DD.md` exists for today; create it if missing.
3. If there was meaningful progress since the last note, append a short checkpoint:
   - Done
   - In progress
   - Next step
4. If there is no new information to record and nothing urgent to notify, reply exactly `HEARTBEAT_OK`.

If user asks for periodic operational checks (weather/calendar/inbox), add them below this section.
