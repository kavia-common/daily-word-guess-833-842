from datetime import datetime, timezone
from typing import List, Dict
import hashlib
import random
from flask import request, make_response
from flask_smorest import Blueprint
from flask.views import MethodView
from marshmallow import Schema, fields, validates, ValidationError

# A small deterministic 6-letter word list
WORD_LIST: List[str] = [
    "OCEANS", "CORALS", "PEARLS", "SAILOR", "MARINE", "BUBBLE", "DOLPHN", "ANCHOR",
    "TIDESY", "REEFUS", "SEABED", "BRIGHT", "PURPLE", "PINKER", "SMOOTH", "STREAM",
    "GLOWER", "WAVING", "SPRITZ", "VIVIFY",
]

MAX_ATTEMPTS = 5
WORD_LENGTH = 6

# Simple in-memory per-day, per-token store
# Structure: store[token][yyyymmdd] = {"attempts": [...], "finished": bool, "won": bool}
STORE: Dict[str, Dict[str, Dict]] = {}

blp = Blueprint(
    "Game",
    "game",
    url_prefix="/api",
    description="Game endpoints for the Daily Word game",
)

def today_key() -> str:
    now = datetime.now(timezone.utc)
    return now.strftime("%Y%m%d")

def select_daily_word(date_key: str) -> str:
    # Deterministic index based on date
    h = hashlib.sha256(date_key.encode("utf-8")).hexdigest()
    idx = int(h, 16) % len(WORD_LIST)
    return WORD_LIST[idx].upper()

def ensure_token() -> str:
    token = request.cookies.get("wg_token")
    if not token:
        # create a token based on random + time; not cryptographically strong but fine for demo
        token = hashlib.sha256(f"{random.random()}-{datetime.utcnow().isoformat()}".encode()).hexdigest()
    return token

def get_state_for_today(token: str) -> Dict:
    date = today_key()
    if token not in STORE:
        STORE[token] = {}
    if date not in STORE[token]:
        STORE[token][date] = {"attempts": [], "finished": False, "won": False}
    return STORE[token][date]

def score_guess(guess: str, answer: str) -> List[str]:
    """
    Returns list of colors per position: 'green', 'yellow', 'grey'
    """
    res = ["grey"] * WORD_LENGTH
    answer_chars = list(answer)

    # First pass greens
    for i, ch in enumerate(guess):
        if answer[i] == ch:
            res[i] = "green"
            answer_chars[i] = None  # consume

    # Second pass yellows
    for i, ch in enumerate(guess):
        if res[i] == "green":
            continue
        if ch in answer_chars:
            res[i] = "yellow"
            # consume first occurrence
            answer_chars[answer_chars.index(ch)] = None

    return res

class GuessRequestSchema(Schema):
    # PUBLIC_INTERFACE
    def __init__(self, *args, **kwargs):
        """Schema for guess request."""
        super().__init__(*args, **kwargs)

    guess = fields.String(
        required=True,
        validate=lambda s: isinstance(s, str) and len(s) == WORD_LENGTH and s.isalpha(),
        description=f"A {WORD_LENGTH}-letter guess (alphabetic only).",
    )

    @validates("guess")
    def validate_guess(self, value: str) -> None:
        v = value.strip()
        if len(v) != WORD_LENGTH or not v.isalpha():
            raise ValidationError(f"Guess must be exactly {WORD_LENGTH} letters.")
        return None

class GuessResponseSchema(Schema):
    feedback = fields.List(fields.String(), required=True, description="Per-letter feedback: green, yellow, grey")
    attempts_used = fields.Integer(required=True, description="Number of attempts used so far (including this one)")
    max_attempts = fields.Integer(required=True, description="Maximum attempts allowed per day")
    status = fields.String(required=True, description="Game status after the guess: in_progress | won | lost")
    message = fields.String(required=True, description="Human-readable status message")

class StatusResponseSchema(Schema):
    date = fields.String(required=True, description="YYYYMMDD for today's game")
    attempts = fields.List(fields.List(fields.String()), required=True, description="List of feedback arrays for previous guesses")
    guesses = fields.List(fields.String(), required=True, description="List of previous guess strings")
    attempts_used = fields.Integer(required=True, description="Number of attempts used")
    max_attempts = fields.Integer(required=True, description="Maximum attempts allowed per day")
    status = fields.String(required=True, description="in_progress | won | lost")
    message = fields.String(required=True, description="Human-readable message")

@blp.route("/status")
class GameStatus(MethodView):
    """
    Get the current game status for the caller's session for the current day.
    Sets a cookie token if one is not present to track attempts per day.
    """

    # PUBLIC_INTERFACE
    def get(self):
        """Get daily game status for the session."""
        token = ensure_token()
        date = today_key()
        answer = select_daily_word(date)
        state = get_state_for_today(token)

        attempts_feedback = []
        guesses = []
        for entry in state["attempts"]:
            guesses.append(entry["guess"])
            attempts_feedback.append(entry["feedback"])

        status = "won" if state["won"] else ("lost" if state["finished"] and not state["won"] else "in_progress")
        msg = "Make your guess!" if status == "in_progress" else ("You won! 🎉" if status == "won" else f"Out of attempts. The word was {answer}.")

        payload = {
            "date": date,
            "attempts": attempts_feedback,
            "guesses": guesses,
            "attempts_used": len(state["attempts"]),
            "max_attempts": MAX_ATTEMPTS,
            "status": status,
            "message": msg,
        }
        resp = make_response(payload, 200)
        # Set cookie if not present
        if not request.cookies.get("wg_token"):
            resp.set_cookie("wg_token", token, httponly=False, samesite="Lax")
        return resp

@blp.route("/guess")
class GameGuess(MethodView):
    """
    Submit a guess for today's word. Requires a 6-letter alphabetic guess.
    Returns per-letter feedback.
    """

    # PUBLIC_INTERFACE
    @blp.arguments(GuessRequestSchema, location="json")
    @blp.response(200, GuessResponseSchema)
    def post(self, json_data):
        """Submit a guess and receive feedback."""
        token = ensure_token()
        date = today_key()
        answer = select_daily_word(date)
        state = get_state_for_today(token)

        if state["finished"]:
            status = "won" if state["won"] else "lost"
            message = "Game already finished for today."
            return {
                "feedback": [],
                "attempts_used": len(state["attempts"]),
                "max_attempts": MAX_ATTEMPTS,
                "status": status,
                "message": message,
            }

        guess_raw = json_data["guess"]
        guess = guess_raw.strip().upper()

        if len(guess) != WORD_LENGTH or not guess.isalpha():
            raise ValidationError(f"Guess must be exactly {WORD_LENGTH} letters.")

        feedback = score_guess(guess, answer)
        state["attempts"].append({"guess": guess, "feedback": feedback})

        won = all(x == "green" for x in feedback)
        if won:
            state["finished"] = True
            state["won"] = True
            status = "won"
            message = "Correct! 🎉"
        elif len(state["attempts"]) >= MAX_ATTEMPTS:
            state["finished"] = True
            state["won"] = False
            status = "lost"
            message = f"No attempts left. The word was {answer}."
        else:
            status = "in_progress"
            message = "Good try! Keep going."

        resp = make_response(
            {
                "feedback": feedback,
                "attempts_used": len(state["attempts"]),
                "max_attempts": MAX_ATTEMPTS,
                "status": status,
                "message": message,
            },
            200,
        )
        if not request.cookies.get("wg_token"):
            resp.set_cookie("wg_token", token, httponly=False, samesite="Lax")
        return resp
