import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash")
ONTOLOGY_PATH = ROOT / os.getenv("ONTOLOGY_PATH", "ontology/degree_audit.ttl")


def llm_ready() -> bool:
    return bool(GEMINI_API_KEY) and GEMINI_API_KEY != "your_api_key_here"
