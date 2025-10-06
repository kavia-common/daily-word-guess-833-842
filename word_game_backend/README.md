# Daily Word Game Backend (Flask)

Runs a small API for a daily 6-letter word game.

Endpoints
- GET /api/status
  Returns current game state for this session (tracked via cookie `wg_token`).
- POST /api/guess
  Body: { "guess": "LETTER" } where LETTER is a 6-letter alphabetic string.
  Returns per-letter feedback: green, yellow, grey.

CORS
- Enabled for http://localhost:3000 on /api/*.

Run locally
- Python 3.11+
- Install dependencies:
  pip install -r requirements.txt
- Start server on port 3001:
  python run.py

OpenAPI/Docs
- Swagger UI at /docs
- Raw spec at /docs/openapi.json

Notes
- In-memory session store for demo; resets on server restart.
- Daily word is deterministic by date from a small list.
