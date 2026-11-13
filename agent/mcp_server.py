"""MCP server exposing the seven degree audit tools.

Run from the project root:
    python agent/mcp_server.py
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mcp.server.fastmcp import FastMCP

from audit import queries

mcp = FastMCP("degree-audit")


@mcp.tool()
def get_student_summary(student: str) -> dict:
    """Return a student's CGPA, earned credits, academic standing and advisor."""
    return queries.get_student_summary(student)


@mcp.tool()
def get_completed_courses(student: str) -> list[str]:
    """Return the course codes a student has passed."""
    return queries.get_completed_courses(student)


@mcp.tool()
def get_next_eligible_courses(student: str) -> list[str]:
    """Return the course codes a student can take next because every prerequisite is passed."""
    return queries.get_next_eligible_courses(student)


@mcp.tool()
def get_prerequisite_chain(course_code: str) -> list[str]:
    """Return all direct and indirect prerequisites of a course, for example ML402."""
    return queries.get_prerequisite_chain(course_code)


@mcp.tool()
def get_credits_remaining(student: str) -> int:
    """Return how many credits a student still needs to graduate."""
    return queries.get_credits_remaining(student)


@mcp.tool()
def get_standing(student: str) -> str:
    """Return a student's academic standing: Probation, At Risk, Dean's List, Graduation Eligible or Good Standing."""
    return queries.get_standing(student)


@mcp.tool()
def get_courses_to_retake(student: str) -> list[str]:
    """Return the course codes a student failed and must retake."""
    return queries.get_courses_to_retake(student)


if __name__ == "__main__":
    mcp.run()
