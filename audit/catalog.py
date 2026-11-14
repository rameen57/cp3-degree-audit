"""UCP course catalog and prerequisite helpers.

The base catalog lives in ``data/ucp_catalog.json``. Courses added by the user
from the Course Planner are kept separately in ``data/custom_courses.json`` so
the published UCP data is never modified.
"""

from __future__ import annotations

import json
import re
from collections import deque
from typing import Any

from google import genai
from google.genai import types

from audit.config import GEMINI_API_KEY, GEMINI_MODEL, ROOT, llm_ready

CATALOG_PATH = ROOT / "data" / "ucp_catalog.json"
CUSTOM_PATH = ROOT / "data" / "custom_courses.json"

COURSE_CODE_RE = re.compile(r"^[A-Z0-9][A-Z0-9_-]{1,15}$")

GRADE_POINTS = {
    "A+": 4.0,
    "A": 4.0,
    "A-": 3.7,
    "B+": 3.3,
    "B": 3.0,
    "B-": 2.7,
    "C+": 2.3,
    "C": 2.0,
    "C-": 1.7,
    "D+": 1.3,
    "D": 1.0,
    "F": 0.0,
}
NON_GRADED = {
    "IP": "In progress",
    "IN PROGRESS": "In progress",
    "I": "Incomplete",
    "W": "Withdrawn",
    "WF": "Withdrawn failing",
}
GRADE_OPTIONS = list(GRADE_POINTS) + ["IP", "I", "W"]

_BASE: dict[str, Any] | None = None
_CUSTOM: dict[str, Any] | None = None
_CACHE: tuple[dict[str, dict[str, Any]], list[dict[str, Any]], dict[str, str]] | None = None


def _read_json(path, default: dict[str, Any]) -> dict[str, Any]:
    if not path.exists():
        return default
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Could not read {path.name}: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError(f"{path.name} must contain a JSON object.")
    return data


def _write_json(path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def _base_data() -> dict[str, Any]:
    global _BASE
    if _BASE is None:
        _BASE = _read_json(CATALOG_PATH, {"programs": [], "courses": []})
        if not _BASE.get("programs") or not _BASE.get("courses"):
            raise ValueError("The UCP catalog is empty or incomplete.")
    return _BASE


def _custom_data() -> dict[str, Any]:
    global _CUSTOM
    if _CUSTOM is None:
        _CUSTOM = _read_json(CUSTOM_PATH, {"courses": []})
        _CUSTOM.setdefault("courses", [])
    return _CUSTOM


def _program_codes() -> list[str]:
    return [str(program["code"]).upper() for program in _base_data()["programs"]]


def _normalise_programs(raw: Any) -> list[str]:
    known = _program_codes()
    if raw in (None, "", "*", "ALL"):
        return known
    values = [str(item).strip().upper() for item in raw] if isinstance(raw, list) else [str(raw).strip().upper()]
    unknown = [value for value in values if value not in known]
    if unknown:
        raise ValueError(f"Unknown UCP program code(s): {', '.join(unknown)}")
    return sorted(set(values), key=known.index)


def _normalise_course(raw: dict[str, Any], *, custom: bool = False) -> dict[str, Any]:
    code = str(raw.get("code", "")).strip().upper()
    if not COURSE_CODE_RE.fullmatch(code):
        raise ValueError(
            "Course code must start with a letter or digit and use only letters, "
            "digits, underscores or hyphens (2-16 characters)."
        )
    title = str(raw.get("title", "")).strip()
    if not title:
        raise ValueError(f"{code} needs a course title.")
    try:
        credits = int(raw.get("credits", 0))
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{code} needs a whole number of credit hours.") from exc
    if credits < 1 or credits > 6:
        raise ValueError(f"{code} credit hours must be between 1 and 6.")
    prerequisites = sorted(
        {
            str(item).strip().upper()
            for item in raw.get("prerequisites", [])
            if str(item).strip()
        }
    )
    for prerequisite in prerequisites:
        if not COURSE_CODE_RE.fullmatch(prerequisite):
            raise ValueError(f"{code} has an invalid prerequisite code: {prerequisite}")
    category = str(raw.get("category", "Custom" if custom else "Course")).strip()
    return {
        "code": code,
        "title": title,
        "credits": credits,
        "prerequisites": prerequisites,
        "programs": _normalise_programs(raw.get("programs", "*")),
        "category": category,
        "custom": custom,
    }


def _build() -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]], dict[str, str]]:
    global _CACHE
    if _CACHE is not None:
        return _CACHE
    by_code: dict[str, dict[str, Any]] = {}
    for raw in _base_data()["courses"]:
        course = _normalise_course(raw)
        by_code[course["code"]] = course
    for raw in _custom_data()["courses"]:
        course = _normalise_course(raw, custom=True)
        if course["code"] in by_code:
            raise ValueError(
                f"Custom course {course['code']} duplicates a UCP catalog course."
            )
        by_code[course["code"]] = course
    for course in by_code.values():
        missing = [code for code in course["prerequisites"] if code not in by_code]
        if missing:
            raise ValueError(
                f"{course['code']} references unknown prerequisite(s): {', '.join(missing)}"
            )
    programs = {
        str(program["code"]).upper(): str(program["name"])
        for program in _base_data()["programs"]
    }
    courses = sorted(by_code.values(), key=lambda item: item["code"])
    _CACHE = (by_code, courses, programs)
    return _CACHE


def _refresh() -> None:
    global _BASE, _CUSTOM, _CACHE
    _BASE = None
    _CUSTOM = None
    _CACHE = None


def list_programs() -> list[dict[str, Any]]:
    """Return the five UCP IT programs with code, name and credit total."""
    programs = []
    for program in _base_data()["programs"]:
        programs.append(
            {
                "code": str(program["code"]).upper(),
                "name": str(program["name"]),
                "credits": int(program["credits"]),
                "department": str(program.get("department", "UCP")),
            }
        )
    return programs


def program_codes() -> list[str]:
    return [program["code"] for program in list_programs()]


def program_names() -> list[str]:
    return [program["name"] for program in list_programs()]


def resolve_program(value: str) -> str:
    """Resolve a UCP program code or full name to its code."""
    text = str(value or "").strip().lower()
    for program in list_programs():
        if text in {program["code"].lower(), program["name"].lower()}:
            return program["code"]
    raise ValueError(f"Unknown UCP program: {value}. Choose one of {', '.join(program_codes())}.")


def get_program(value: str) -> dict[str, Any]:
    code = resolve_program(value)
    return next(program for program in list_programs() if program["code"] == code)


def program_name(value: str) -> str:
    try:
        return get_program(value)["name"]
    except ValueError:
        return str(value)


def all_courses(program: str | None = None) -> list[dict[str, Any]]:
    """Return every catalog course, optionally filtered to one UCP program."""
    _, courses, _ = _build()
    if not program:
        return [dict(course) for course in courses]
    code = resolve_program(program)
    return [dict(course) for course in courses if code in course["programs"]]


def get_course(course_code: str) -> dict[str, Any] | None:
    by_code, _, _ = _build()
    code = str(course_code or "").strip().upper()
    course = by_code.get(code)
    return dict(course) if course else None


def require_course(course_code: str) -> dict[str, Any]:
    course = get_course(course_code)
    if course is None:
        raise ValueError(f"Unknown UCP course: {course_code}")
    return course


def search_courses(
    query: str = "",
    program: str | None = None,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    """Search codes and titles across the catalog."""
    text = str(query or "").strip().lower()
    courses = all_courses(program)
    if text:
        courses = [
            course
            for course in courses
            if text in course["code"].lower() or text in course["title"].lower()
        ]
    if limit:
        return courses[:limit]
    return courses


search_ucp_courses = search_courses


def prerequisite_chain(course_code: str) -> list[str]:
    """Return all direct and indirect prerequisite codes of a course."""
    by_code, _, _ = _build()
    start = str(course_code or "").strip().upper()
    if start not in by_code:
        raise ValueError(f"Unknown UCP course: {course_code}")
    seen: set[str] = set()
    queue = deque(by_code[start]["prerequisites"])
    while queue:
        code = queue.popleft()
        if code in seen or code not in by_code:
            continue
        seen.add(code)
        queue.extend(by_code[code]["prerequisites"])
    return sorted(seen)


def direct_unlocks(course_code: str) -> list[str]:
    """Return courses that list the given course as a direct prerequisite."""
    _, courses, _ = _build()
    code = str(course_code or "").strip().upper()
    return sorted(
        course["code"] for course in courses if code in course["prerequisites"]
    )


def unlocks(course_code: str) -> list[str]:
    """Return every course unlocked directly or indirectly by a course."""
    _, courses, _ = _build()
    code = str(course_code or "").strip().upper()
    return sorted(
        course["code"] for course in courses if code in prerequisite_chain(course["code"])
    )


def top_unlockers(program: str | None = None, limit: int = 5) -> list[dict[str, Any]]:
    courses = all_courses(program)
    candidates = [
        (course["code"], len(unlocks(course["code"])))
        for course in courses
        if unlocks(course["code"])
    ]
    return [
        {"code": code, "unlocks": count}
        for code, count in sorted(candidates, key=lambda item: (-item[1], item[0]))[:limit]
    ]


def prerequisite_edges(program: str | None = None) -> list[dict[str, str]]:
    courses = all_courses(program)
    allowed = {course["code"] for course in courses}
    return [
        {"from": prerequisite, "to": course["code"]}
        for course in courses
        for prerequisite in course["prerequisites"]
        if prerequisite in allowed
    ]


def catalog_metrics() -> dict[str, int]:
    _, courses, _ = _build()
    return {
        "programs": len(list_programs()),
        "courses": len(courses),
        "customCourses": sum(1 for course in courses if course["custom"]),
        "creditHours": sum(course["credits"] for course in courses),
        "prerequisiteEdges": sum(len(course["prerequisites"]) for course in courses),
    }


def program_summary(program: str) -> dict[str, Any]:
    code = resolve_program(program)
    courses = all_courses(code)
    categories: dict[str, dict[str, int]] = {}
    for course in courses:
        bucket = categories.setdefault(
            course["category"], {"courses": 0, "credits": 0}
        )
        bucket["courses"] += 1
        bucket["credits"] += course["credits"]
    return {
        **get_program(code),
        "catalogCourses": len(courses),
        "catalogCredits": sum(course["credits"] for course in courses),
        "categories": categories,
    }


def verify_grade(grade: str) -> dict[str, Any]:
    """Verify a UCP letter grade and decide whether the course is passed."""
    text = str(grade or "").strip().upper().replace(" ", " ")
    if text in NON_GRADED:
        return {
            "grade": text,
            "points": None,
            "passed": False,
            "countsCredits": False,
            "message": f"{NON_GRADED[text]} - not counted as passed or earned.",
        }
    if text not in GRADE_POINTS:
        raise ValueError(
            f"Unknown grade {grade!r}. Use one of {', '.join(GRADE_OPTIONS)}."
        )
    points = GRADE_POINTS[text]
    passed = points >= 1.0
    return {
        "grade": text,
        "points": points,
        "passed": passed,
        "countsCredits": passed,
        "message": (
            f"{text} is a passing grade (D or better) and earns credit."
            if passed
            else f"{text} is a failing grade; the course must be retaken."
        ),
    }


def estimate_cgpa(courses: list[dict[str, Any]]) -> float:
    """Estimate CGPA from the graded courses currently stored in the profile."""
    weighted = 0.0
    credits = 0
    for course in courses:
        grade = str(course.get("grade", "")).strip().upper()
        if grade not in GRADE_POINTS:
            continue
        hours = int(course.get("credits", 0) or 0)
        weighted += GRADE_POINTS[grade] * hours
        credits += hours
    return round(weighted / credits, 2) if credits else 0.0


def search_ucp_web(query: str) -> dict[str, Any]:
    """Google Search grounding for official UCP information.

    This is a function tool so the agent can decide when to use it. It returns
    the model's grounded answer plus any source URLs it could extract.
    """
    if not llm_ready():
        return {
            "answer": "Web search is unavailable because no Gemini API key is configured.",
            "sources": [],
        }
    client = genai.Client(api_key=GEMINI_API_KEY)
    try:
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=(
                "Search official University of Central Punjab information for: "
                f"{query}\n"
                "Answer only UCP facts. If sources are found, list their URLs at the end."
            ),
            config=types.GenerateContentConfig(
                tools=[types.Tool(google_search=types.GoogleSearch())],
                temperature=0.1,
            ),
        )
        answer = response.text or ""
        sources: list[str] = []
        try:
            candidates = getattr(response, "candidates", None) or []
            for candidate in candidates:
                metadata = getattr(candidate, "grounding_metadata", None)
                chunks = getattr(metadata, "grounding_chunks", None) or []
                for chunk in chunks:
                    web = getattr(chunk, "web", None)
                    uri = getattr(web, "uri", None) if web else None
                    title = getattr(web, "title", None) if web else None
                    if uri and uri not in sources:
                        sources.append(uri)
        except Exception:
            pass
        return {"answer": answer, "sources": sources}
    except Exception as exc:
        return {
            "answer": f"UCP web search is unavailable right now ({type(exc).__name__}).",
            "sources": [],
        }


def custom_courses() -> list[dict[str, Any]]:
    return [dict(course) for course in _build()[1] if course["custom"]]


def add_custom_course(
    code: str,
    title: str,
    credits: int,
    prerequisites: list[str] | None = None,
    programs: list[str] | None = None,
) -> dict[str, Any]:
    """Add or update a user-created course in the local catalog overlay."""
    normalised = _normalise_course(
        {
            "code": code,
            "title": title,
            "credits": credits,
            "prerequisites": prerequisites or [],
            "programs": programs or [program_codes()[0]],
            "category": "Custom",
        },
        custom=True,
    )
    base_codes = {str(raw["code"]).upper() for raw in _base_data()["courses"]}
    if normalised["code"] in base_codes:
        raise ValueError(
            f"{normalised['code']} already exists in the official UCP catalog."
        )
    custom_codes = {
        str(raw.get("code", "")).upper() for raw in _custom_data()["courses"]
    }
    known = (base_codes | custom_codes | {normalised["code"]}) - {normalised["code"]}
    missing = [code for code in normalised["prerequisites"] if code not in known]
    if missing:
        raise ValueError(
            f"Unknown prerequisite(s): {', '.join(missing)}. "
            "Add the prerequisite course first."
        )

    graph: dict[str, list[str]] = {}
    for raw in _base_data()["courses"] + _custom_data()["courses"]:
        code = str(raw.get("code", "")).upper()
        if code and code != normalised["code"]:
            graph[code] = [str(item).upper() for item in raw.get("prerequisites", [])]
    graph[normalised["code"]] = list(normalised["prerequisites"])

    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(node: str) -> None:
        if node in visiting:
            raise ValueError("That prerequisite would create a course dependency cycle.")
        if node in visited or node not in graph:
            return
        visiting.add(node)
        for prerequisite in graph[node]:
            visit(prerequisite)
        visiting.remove(node)
        visited.add(node)

    for node in graph:
        visit(node)

    data = _custom_data()
    stored = [
        item
        for item in data["courses"]
        if str(item.get("code", "")).upper() != normalised["code"]
    ]
    stored.append(normalised)
    data["courses"] = sorted(stored, key=lambda item: str(item["code"]).upper())
    _write_json(CUSTOM_PATH, data)
    _refresh()
    return normalised


def remove_custom_course(course_code: str) -> bool:
    code = str(course_code or "").strip().upper()
    data = _custom_data()
    kept = [item for item in data["courses"] if str(item.get("code", "")).upper() != code]
    if len(kept) == len(data["courses"]):
        return False
    data["courses"] = kept
    _write_json(CUSTOM_PATH, data)
    _refresh()
    return True
