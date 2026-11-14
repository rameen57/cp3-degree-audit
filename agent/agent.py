"""Gemini-powered UCP Degree Audit Assistant.

The agent answers only UCP academic questions: BS Computer Science, BS Data
Science, BS Software Engineering, BS Artificial Intelligence, and BS Cyber
Security at University of Central Punjab. It uses personal profile/catalog
tools and, when the API key is available, Google Search grounding for official
UCP sources. Without a valid API key the Streamlit app still works; Ask the
Agent shows a friendly setup message.
"""

import functools
import sys
from pathlib import Path
from typing import Any

import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from google import genai
from google.genai import types

from audit import catalog, profile
from audit.config import GEMINI_API_KEY, GEMINI_MODEL, llm_ready


@st.cache_resource
def _genai_client(api_key: str):
    return genai.Client(api_key=api_key)

SYSTEM = (
    "You are the Degreely UCP Degree Audit Assistant. "
    "Answer only about University of Central Punjab (UCP) IT-related "
    "undergraduate degrees: BS Computer Science, BS Data Science, BS Software "
    "Engineering, BS Artificial Intelligence, and BS Cyber Security. "
    "If a question is not about UCP, politely refuse and do not answer it. "
    "Use the UCP catalog, prerequisite, profile, standing, and planning tools "
    "first. If the catalog does not have enough information, use "
    "search_ucp_web for official UCP sources. Never invent course codes, "
    "prerequisites, credit hours, grades, or rules. Prefer UCP course codes "
    "over titles. Keep answers short, clear, and friendly. If Google Search is "
    "unavailable, say so and answer from the catalog/profile when possible."
)

COMPLEX_KEYWORDS = {
    "course",
    "prerequisite",
    "prereq",
    "credit",
    "standing",
    "dean",
    "probation",
    "graduation",
    "eligible",
    "retake",
    "plan",
    "unlock",
    "ucp",
    "bs cs",
    "bsds",
    "bsse",
    "bsai",
    "bscy",
    "degree",
    "audit",
    "transcript",
    "semester",
    "grades",
    "grade",
    "pass",
    "fail",
}

TOOLS = [
    profile.get_my_profile,
    profile.get_my_courses,
    profile.get_my_standing,
    profile.get_my_remaining_credits,
    profile.get_my_eligible_courses,
    profile.plan_ucp_course,
    catalog.search_ucp_courses,
    catalog.get_course,
    catalog.verify_grade,
    catalog.search_ucp_web,
]


def traced(function, log: list[str]):
    @functools.wraps(function)
    def wrapper(*args, **kwargs):
        log.append(function.__name__)
        return function(*args, **kwargs)

    return wrapper


def _profile_summary() -> str:
    try:
        summary = profile.summary()
    except Exception:
        return ""
    p = summary["profile"]
    program = summary["program"]
    return (
        f" Current profile: {p.get('name') or 'not set'}, roll "
        f"{p.get('roll_number') or 'not set'}, {program['name']}, "
        f"{p.get('semester') or 'not set'}, CGPA {p.get('cgpa', 0):.2f}, "
        f"credits passed {summary['creditsPassed']} of {program['credits']}, "
        f"remaining {summary['creditsRemaining']}, standing {summary['standing']}."
    )


def _system_instruction(student: str = "") -> str:
    instruction = SYSTEM + _profile_summary()
    if student:
        instruction += f" The caller also mentioned student context: {student}."
    return instruction


def _simple_direct_answer(question: str, profile_data: dict[str, Any]) -> str | None:
    """Answer greetings and simple profile-only questions without an LLM/tool loop."""
    q = question.strip().lower()
    greetings = {
        "hi", "hello", "hey", "good morning", "good afternoon", "good evening",
        "thanks", "thank you", "bye",
    }
    if q in greetings:
        return "Hello! I'm your UCP Degree Audit Assistant. Ask me about your UCP courses, prerequisites, credits, standing, or profile."

    simple_profile = {
        "name", "roll", "roll number", "profile", "gpa", "cgpa", "who am i",
        "my name", "my roll", "my gpa", "my cgpa", "my profile",
    }
    if any(k in q for k in simple_profile) and not any(k in q for k in COMPLEX_KEYWORDS):
        name = profile_data.get("name") or ""
        roll = profile_data.get("roll_number") or ""
        program = catalog.program_name(profile_data.get("program", "BSCS"))
        semester = profile_data.get("semester") or "not set"
        cgpa = profile_data.get("cgpa", 0.0)
        if not name and not roll:
            return "You haven't saved a profile yet. Go to Overview and save your name, roll number, program, semester, and CGPA."
        return (
            f"Your profile: {name or 'not set'}, roll {roll or 'not set'}, "
            f"{program}, {semester}, CGPA {cgpa:.2f}."
        )
    return None


def ask(question: str, student: str = "") -> dict:
    """Answer a UCP-scoped question using catalog/profile/tools and web search."""
    profile_data = profile.load_profile()
    direct = _simple_direct_answer(question, profile_data)
    if direct is not None:
        return {"answer": direct, "tools_used": []}

    if not llm_ready():
        return {
            "answer": "Add your Gemini API key to the .env file to use the UCP agent.",
            "tools_used": [],
        }
    if not question or not question.strip():
        return {
            "answer": "Ask me about UCP courses, prerequisites, credits, standing, or your profile.",
            "tools_used": [],
        }

    calls: list[str] = []
    client = _genai_client(GEMINI_API_KEY)
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
        answer = response.text or "I could not produce an answer from the UCP catalog and your profile."
    except Exception as exc:  # keep the UI alive if the API or model is unavailable
        return {
            "answer": f"The UCP agent could not answer right now: {exc}",
            "tools_used": calls,
        }

    return {"answer": answer, "tools_used": calls}
