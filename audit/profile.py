"""Persistent personal degree-audit profile.

The published ontology and UCP catalog stay read-only. A student's editable
profile is stored in ``data/my_profile.json`` and all progress calculations in
this module are derived from that file plus the catalog.
"""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from typing import Any

from audit import catalog
from audit.config import ROOT

PROFILE_PATH = ROOT / "data" / "my_profile.json"

# In-memory profile cache so the JSON file is parsed once per session unless
# it is modified by Save profile.
_PROFILE_CACHE: dict[str, Any] | None = None
_PROFILE_MTIME: float | None = None


DEFAULT_SEMESTERS = [
    "Semester 1",
    "Semester 2",
    "Semester 3",
    "Semester 4",
    "Semester 5",
    "Semester 6",
    "Semester 7",
    "Semester 8",
]


def default_profile() -> dict[str, Any]:
    program = "BSCS"
    return {
        "name": "",
        "roll_number": "",
        "program": program,
        "semester": "Semester 1",
        "cgpa": 0.0,
        "courses": [],
        "planned_courses": [],
        "updated_at": "",
    }


DEFAULT_TERMS = [
    "Fall 2024",
    "Spring 2025",
    "Summer 2025",
    "Fall 2025",
    "Spring 2026",
    "Summer 2026",
    "Fall 2026",
    "Spring 2027",
]


def _safe_program(value: Any) -> str:
    try:
        return catalog.resolve_program(str(value or ""))
    except ValueError:
        return "BSCS"


def _safe_semester(value: Any) -> str:
    text = str(value or "").strip()
    return text[:60] if text else "Semester 1"


def _safe_cgpa(value: Any) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return 0.0
    return round(min(max(number, 0.0), 4.0), 2)


def _normalise_record(raw: dict[str, Any], profile: dict[str, Any]) -> dict[str, Any]:
    code = str(raw.get("code", "")).strip().upper()
    course = catalog.get_course(code)
    if course is None:
        raise ValueError(f"Unknown UCP course in profile: {code}")
    grade_info = catalog.verify_grade(str(raw.get("grade", "")))
    return {
        "code": course["code"],
        "title": course["title"],
        "credits": course["credits"],
        "prerequisites": course["prerequisites"],
        "category": course["category"],
        "programs": course["programs"],
        "custom": course["custom"],
        "grade": grade_info["grade"],
        "points": grade_info["points"],
        "passed": grade_info["passed"],
        "counts_credits": grade_info["countsCredits"],
        "verification": grade_info["message"],
        "semester": _safe_semester(raw.get("semester", profile["semester"])),
    }


def normalise_profile(raw: dict[str, Any]) -> dict[str, Any]:
    profile = default_profile()
    if not isinstance(raw, dict):
        return profile
    profile["name"] = str(raw.get("name", "")).strip()[:100]
    profile["roll_number"] = str(raw.get("roll_number", "")).strip()[:60]
    profile["program"] = _safe_program(raw.get("program"))
    profile["semester"] = _safe_semester(raw.get("semester"))
    profile["cgpa"] = _safe_cgpa(raw.get("cgpa"))
    profile["updated_at"] = str(raw.get("updated_at", ""))
    records: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in raw.get("courses", []):
        if not isinstance(item, dict):
            continue
        try:
            record = _normalise_record(item, profile)
        except ValueError:
            continue
        if record["code"] in seen:
            continue
        seen.add(record["code"])
        records.append(record)
    profile["courses"] = sorted(records, key=lambda item: (item["semester"], item["code"]))
    planned: list[str] = []
    for item in raw.get("planned_courses", []):
        code = str(item or "").strip().upper()
        if catalog.get_course(code) and code not in planned:
            planned.append(code)
    profile["planned_courses"] = planned
    return profile


def load_profile() -> dict[str, Any]:
    """Load the personal profile, cached in memory until the JSON file changes."""
    global _PROFILE_CACHE, _PROFILE_MTIME
    mtime = None
    raw = None
    if PROFILE_PATH.exists():
        try:
            mtime = PROFILE_PATH.stat().st_mtime
            raw = json.loads(PROFILE_PATH.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            raw = None

    if _PROFILE_CACHE is not None and _PROFILE_MTIME == mtime:
        return _PROFILE_CACHE

    if raw is None:
        profile = default_profile()
    else:
        profile = normalise_profile(raw)
    _PROFILE_CACHE = profile
    _PROFILE_MTIME = mtime
    return profile


def _write_profile(profile: dict[str, Any]) -> None:
    PROFILE_PATH.parent.mkdir(parents=True, exist_ok=True)
    temporary = PROFILE_PATH.with_suffix(".json.tmp")
    temporary.write_text(
        json.dumps(profile, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    temporary.replace(PROFILE_PATH)


def save_profile(profile: dict[str, Any]) -> dict[str, Any]:
    """Validate and persist profile fields, returning the stored profile."""
    global _PROFILE_CACHE, _PROFILE_MTIME
    clean = normalise_profile(profile)
    clean["updated_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    _write_profile(clean)
    _PROFILE_CACHE = clean
    if PROFILE_PATH.exists():
        _PROFILE_MTIME = PROFILE_PATH.stat().st_mtime
    else:
        _PROFILE_MTIME = time.time()
    return clean


def update_profile(**fields: Any) -> dict[str, Any]:
    profile = load_profile()
    profile.update(fields)
    return save_profile(profile)


def _find_record(profile: dict[str, Any], code: str) -> dict[str, Any] | None:
    code = str(code or "").strip().upper()
    return next((item for item in profile["courses"] if item["code"] == code), None)


def get_my_profile() -> dict[str, Any]:
    return load_profile()


def get_my_courses() -> list[dict[str, Any]]:
    return summary()["courses"]


def get_my_standing() -> dict[str, Any]:
    summary_data = summary()
    profile_data = summary_data["profile"]
    program = summary_data["program"]
    return {
        "standing": summary_data["standing"],
        "cgpa": float(profile_data["cgpa"]),
        "creditsPassed": summary_data["creditsPassed"],
        "creditsRemaining": summary_data["creditsRemaining"],
        "creditsRequired": program["credits"],
        "program": program,
        "deanList": summary_data["deanList"],
    }


def get_my_remaining_credits() -> int:
    return summary()["creditsRemaining"]


def get_my_eligible_courses() -> list[dict[str, Any]]:
    return summary()["eligible"]


def add_course(
    code: str,
    grade: str,
    semester: str = "",
    profile: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Verify a course result, store it, and return prerequisites and unlocks."""
    profile = profile or load_profile()
    course = catalog.require_course(code)
    grade_info = catalog.verify_grade(grade)
    record = _normalise_record(
        {
            "code": course["code"],
            "grade": grade_info["grade"],
            "semester": semester or profile["semester"],
        },
        profile,
    )
    existing = _find_record(profile, course["code"])
    action = "updated" if existing else "added"
    profile["courses"] = [
        item for item in profile["courses"] if item["code"] != course["code"]
    ]
    profile["courses"].append(record)
    profile["courses"] = sorted(
        profile["courses"], key=lambda item: (item["semester"], item["code"])
    )
    profile["planned_courses"] = [
        item for item in profile["planned_courses"] if item != course["code"]
    ]
    saved = save_profile(profile)
    plan = plan_course(course["code"], saved)
    return {
        "action": action,
        "record": record,
        "verification": grade_info,
        "plan": plan,
        "profile": saved,
    }


def remove_course(code: str, profile: dict[str, Any] | None = None) -> dict[str, Any]:
    profile = profile or load_profile()
    code = str(code or "").strip().upper()
    before = len(profile["courses"])
    profile["courses"] = [item for item in profile["courses"] if item["code"] != code]
    saved = save_profile(profile)
    return {"removed": len(profile["courses"]) < before, "profile": saved}


def clear_courses(profile: dict[str, Any] | None = None) -> dict[str, Any]:
    profile = profile or load_profile()
    profile["courses"] = []
    profile["planned_courses"] = []
    return save_profile(profile)


def add_planned(code: str, profile: dict[str, Any] | None = None) -> dict[str, Any]:
    profile = profile or load_profile()
    course = catalog.require_course(code)
    if course["code"] not in profile["planned_courses"]:
        profile["planned_courses"].append(course["code"])
    return save_profile(profile)


def remove_planned(code: str, profile: dict[str, Any] | None = None) -> dict[str, Any]:
    profile = profile or load_profile()
    code = str(code or "").strip().upper()
    profile["planned_courses"] = [
        item for item in profile["planned_courses"] if item != code
    ]
    return save_profile(profile)


def _standing(cgpa: float, credits: int, required_credits: int) -> str:
    if cgpa < 2.0:
        return "Probation"
    if cgpa < 2.5:
        return "At Risk"
    if cgpa >= 3.5:
        return "Dean's List"
    if credits >= required_credits:
        return "Graduation Eligible"
    return "Good Standing"


def course_status(profile: dict[str, Any]) -> dict[str, set[str]]:
    passed = {item["code"] for item in profile["courses"] if item["counts_credits"]}
    failed = {
        item["code"]
        for item in profile["courses"]
        if not item["counts_credits"] and item["grade"] in catalog.GRADE_POINTS
    }
    return {"passed": passed, "failed": failed - passed}


def missing_prerequisites(
    course_code: str,
    profile: dict[str, Any] | None = None,
    *,
    full_chain: bool = False,
) -> list[str]:
    profile = profile or load_profile()
    course = catalog.require_course(course_code)
    status = course_status(profile)
    required = (
        catalog.prerequisite_chain(course["code"])
        if full_chain
        else course["prerequisites"]
    )
    return sorted(code for code in required if code not in status["passed"])


def eligible_courses(profile: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    profile = profile or load_profile()
    status = course_status(profile)
    pending = {
        item["code"]
        for item in profile["courses"]
        if item["grade"] not in catalog.GRADE_POINTS
    }
    eligible = []
    for course in catalog.all_courses(profile["program"]):
        if course["code"] in status["passed"] or course["code"] in pending:
            continue
        if all(code in status["passed"] for code in course["prerequisites"]):
            eligible.append(course)
    return eligible


def remaining_courses(profile: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """Return required-program courses that are not yet passed."""
    profile = profile or load_profile()
    status = course_status(profile)
    return [
        course
        for course in catalog.all_courses(profile["program"])
        if course["code"] not in status["passed"]
    ]


def plan_course(
    course_code: str,
    profile: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a planner explanation for one course."""
    profile = profile or load_profile()
    course = catalog.require_course(course_code)
    status = course_status(profile)
    direct_missing = [
        code for code in course["prerequisites"] if code not in status["passed"]
    ]
    chain = catalog.prerequisite_chain(course["code"])
    full_missing = [code for code in chain if code not in status["passed"]]
    unlocked = catalog.unlocks(course["code"])
    pending = {
        item["code"]
        for item in profile["courses"]
        if item["grade"] not in catalog.GRADE_POINTS
    }
    if course["code"] in status["passed"]:
        state = "completed"
        message = f"{course['code']} is already passed."
    elif course["code"] in pending:
        state = "in_progress"
        message = f"{course['code']} is already recorded as in progress or incomplete."
    elif direct_missing:
        state = "locked"
        message = (
            f"{course['code']} is locked. Complete "
            f"{', '.join(direct_missing)} first."
        )
    elif course["code"] in status["failed"]:
        state = "retake"
        message = (
            f"All prerequisites are met. {course['code']} is a retake "
            "because the last recorded grade was failing."
        )
    else:
        state = "ready"
        message = f"{course['code']} is ready: every prerequisite is satisfied."
    return {
        "course": course,
        "state": state,
        "message": message,
        "directMissing": sorted(direct_missing),
        "fullMissing": sorted(full_missing),
        "fullChain": chain,
        "unlocks": unlocked,
        "inProgram": profile["program"] in course["programs"],
        "planned": course["code"] in profile["planned_courses"],
    }


plan_ucp_course = plan_course


def summary(profile: dict[str, Any] | None = None) -> dict[str, Any]:
    profile = profile or load_profile()
    program = catalog.get_program(profile["program"])
    records = profile["courses"]
    passed_records = [item for item in records if item["counts_credits"]]
    failed_records = [
        item
        for item in records
        if not item["counts_credits"] and item["grade"] in catalog.GRADE_POINTS
    ]
    pending_records = [
        item for item in records if item["grade"] not in catalog.GRADE_POINTS
    ]
    credits_passed = sum(item["credits"] for item in passed_records)
    remaining = max(program["credits"] - credits_passed, 0)
    progress = min(100.0, credits_passed / program["credits"] * 100)
    standing = _standing(profile["cgpa"], credits_passed, program["credits"])
    status = course_status(profile)
    gaps = []
    for record in passed_records:
        missing = [
            code
            for code in record["prerequisites"]
            if code not in status["passed"]
        ]
        if missing:
            gaps.append({"code": record["code"], "missing": sorted(missing)})
    return {
        "profile": profile,
        "program": program,
        "courses": records,
        "passed": passed_records,
        "failed": failed_records,
        "pending": pending_records,
        "creditsPassed": credits_passed,
        "creditsRemaining": remaining,
        "progress": round(progress, 1),
        "standing": standing,
        "deanList": standing == "Dean's List",
        "eligible": eligible_courses(profile),
        "planned": [
            course
            for code in profile["planned_courses"]
            if (course := catalog.get_course(code))
        ],
        "prerequisiteGaps": gaps,
        "gpaFromCourses": catalog.estimate_cgpa(records),
        "hasProfile": bool(profile["name"] or profile["roll_number"] or records),
        "coursesOutsideProgram": [
            item for item in records if profile["program"] not in item["programs"]
        ],
    }
