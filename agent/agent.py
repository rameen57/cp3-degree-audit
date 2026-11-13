"""Gemini-powered Degree Audit Assistant.

The agent answers only from the seven tool results. The Gemini API key is read
from the project .env file; without a key the Streamlit app still works and the
Ask the Agent page shows a friendly setup message.
"""

import functools
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from google import genai
from google.genai import types

from audit import queries
from audit.config import GEMINI_API_KEY, GEMINI_MODEL, llm_ready

SYSTEM = (
    "You are the Degree Audit Assistant for the Degreely app. "
    "Answer only from tool results. If a tool returns nothing, say the ontology "
    "has no data for that question. Never invent grades, courses or rules. "
    "When a student asks what blocks a course, use the prerequisite chain and "
    "the completed courses to name the missing prerequisites. Keep answers short, "
    "clear and friendly. Course codes such as ML402 are preferred over titles."
)

TOOLS = [
    queries.get_student_summary,
    queries.get_completed_courses,
    queries.get_next_eligible_courses,
    queries.get_prerequisite_chain,
    queries.get_credits_remaining,
    queries.get_standing,
    queries.get_courses_to_retake,
]


def traced(function, log: list[str]):
    @functools.wraps(function)
    def wrapper(*args, **kwargs):
        log.append(function.__name__)
        return function(*args, **kwargs)

    return wrapper


def _system_instruction(student: str) -> str:
    try:
        roster = ", ".join(
            f"{item['name']} ({item['id']})" for item in queries.list_students()
        )
    except Exception:
        roster = ""
    instruction = SYSTEM
    if roster:
        instruction += f" Known students: {roster}."
    if student:
        instruction += f" The selected student is {student}."
    return instruction


def ask(question: str, student: str = "") -> dict:
    """Answer a natural-language question using only ontology tool results."""
    if not llm_ready():
        return {
            "answer": "Add your Gemini API key to the .env file to use the agent.",
            "tools_used": [],
        }
    if not question or not question.strip():
        return {
            "answer": "Ask me about courses, prerequisites, credits or standing.",
            "tools_used": [],
        }

    calls: list[str] = []
    client = genai.Client(api_key=GEMINI_API_KEY)
    try:
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=question.strip(),
            config=types.GenerateContentConfig(
                system_instruction=_system_instruction(student),
                tools=[traced(tool, calls) for tool in TOOLS],
                temperature=0.2,
            ),
        )
        answer = (
            response.text
            or "I could not produce an answer from the ontology results."
        )
    except Exception as exc:  # keep the UI alive if the API or model is unavailable
        return {
            "answer": f"The agent could not answer right now: {exc}",
            "tools_used": calls,
        }

    return {"answer": answer, "tools_used": calls}
