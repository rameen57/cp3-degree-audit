"""SPARQL data layer for the University Degree Audit ontology.

Every fact used by the MCP server, the agent and the Streamlit app comes from
this module. The seven tool functions at the top of the file are the tools the
LLM agent can call; the remaining helpers feed the seven app pages.
"""

from __future__ import annotations

import re
from functools import lru_cache
from typing import Any

from rdflib import Graph, Literal

from audit.config import ONTOLOGY_PATH

DA = "http://example.org/ontologies/degree-audit#"

PREFIX = f"""PREFIX da: <{DA}>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX owl: <http://www.w3.org/2002/07/owl#>
PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
"""

# Thresholds from the defined-class expressions in section 3.2.
PROBATION_CGPA = 2.0
AT_RISK_CGPA = 2.5
DEANS_LIST_CGPA = 3.5
GRADUATION_CREDITS = 130

_GRAPH: Graph | None = None


def _graph() -> Graph:
    global _GRAPH
    if _GRAPH is None:
        graph = Graph()
        graph.parse(str(ONTOLOGY_PATH), format="turtle")
        _GRAPH = graph
    return _GRAPH


def local(term: Any) -> str:
    """Return the local name of an IRI or the text of a literal."""
    text = str(term)
    if "#" in text:
        return text.rsplit("#", 1)[-1]
    return text.rstrip("/").rsplit("/", 1)[-1]


def _scalar(term: Any) -> Any:
    if term is None:
        return None
    if isinstance(term, Literal):
        return term.toPython()
    return local(term)


def _display(term: Any) -> str:
    if term is None:
        return ""
    text = str(term)
    if text.startswith("http://www.w3.org/2001/XMLSchema#"):
        return "xsd:" + text.rsplit("#", 1)[-1]
    return local(term)


def _rows(query: str) -> list[dict[str, Any]]:
    result = _graph().query(PREFIX + query)
    return [
        {str(variable): _scalar(row[variable]) for variable in result.vars}
        for row in result
    ]


def clean(name: str) -> str:
    """Validate an identifier before it is placed in a SPARQL query."""
    if not isinstance(name, str) or not re.fullmatch(r"[A-Za-z0-9_]+", name.strip()):
        raise ValueError("Invalid identifier. Use letters, digits and underscore only.")
    return name.strip()


@lru_cache(maxsize=1)
def _student_lookup() -> dict[str, str]:
    rows = _rows(
        """
        SELECT DISTINCT ?student ?name WHERE {
            ?student a da:Student .
            OPTIONAL { ?student da:fullName ?name }
        }
        """
    )
    lookup: dict[str, str] = {}
    for row in rows:
        identifier = row["student"]
        keys = {identifier.lower(), identifier.removeprefix("Student_").lower()}
        if row["name"]:
            keys.add(str(row["name"]).lower())
        for key in keys:
            lookup[key] = identifier
    return lookup


def _student_iri(student: str) -> str:
    if not isinstance(student, str):
        raise ValueError("Invalid student.")
    identifier = _student_lookup().get(student.strip().lower())
    if identifier is None:
        raise ValueError(f"Unknown student: {student}")
    return clean(identifier)


@lru_cache(maxsize=1)
def _course_lookup() -> dict[str, str]:
    rows = _rows(
        """
        SELECT DISTINCT ?course ?code ?title WHERE {
            ?course a ?kind .
            ?kind rdfs:subClassOf* da:Course .
            OPTIONAL { ?course da:courseCode ?code }
            OPTIONAL { ?course da:courseTitle ?title }
        }
        """
    )
    lookup: dict[str, str] = {}
    for row in rows:
        identifier = row["course"]
        keys = {identifier.lower()}
        if row["code"]:
            keys.add(str(row["code"]).lower())
        if row["title"]:
            keys.add(str(row["title"]).lower())
        for key in keys:
            lookup[key] = identifier
    return lookup


def _course_iri(course: str) -> str:
    if not isinstance(course, str):
        raise ValueError("Invalid course.")
    identifier = _course_lookup().get(course.strip().lower())
    if identifier is None:
        raise ValueError(f"Unknown course: {course}")
    return clean(identifier)


def _standing_label(cgpa: float, credits: int) -> str:
    if cgpa < PROBATION_CGPA:
        return "Probation"
    if cgpa < AT_RISK_CGPA:
        return "At Risk"
    if cgpa >= DEANS_LIST_CGPA:
        return "Dean's List"
    if credits >= GRADUATION_CREDITS:
        return "Graduation Eligible"
    return "Good Standing"


############################################################
# The seven agent tools
############################################################


def get_student_summary(student: str) -> dict[str, Any]:
    """Return a student's CGPA, earned credits, academic standing and advisor.

    The student can be an identifier such as Student_Ayesha or a name such as Ayesha.
    """
    iri = _student_iri(student)
    rows = _rows(
        f"""
        SELECT ?name ?cgpa ?credits ?advisor ?advisorName WHERE {{
            da:{iri} da:cgpa ?cgpa ;
                      da:totalCreditsEarned ?credits .
            OPTIONAL {{ da:{iri} da:fullName ?name }}
            OPTIONAL {{
                da:{iri} da:hasAdvisor ?advisor .
                OPTIONAL {{ ?advisor da:fullName ?advisorName }}
            }}
        }}
        LIMIT 1
        """
    )
    if not rows:
        return {}
    row = rows[0]
    cgpa = float(row["cgpa"])
    credits = int(row["credits"])
    advisor = row["advisor"] or ""
    advisor_name = (
        str(row["advisorName"])
        if row["advisorName"]
        else advisor.removeprefix("Advisor_")
    )
    return {
        "student": iri,
        "name": str(row["name"]) if row["name"] else iri.removeprefix("Student_"),
        "cgpa": round(cgpa, 2),
        "totalCreditsEarned": credits,
        "standing": _standing_label(cgpa, credits),
        "advisor": advisor,
        "advisorName": advisor_name,
    }


def get_completed_courses(student: str) -> list[str]:
    """List the course codes a student has passed, for example PF101 and MATH101."""
    iri = _student_iri(student)
    rows = _rows(
        f"""
        SELECT DISTINCT ?code WHERE {{
            da:{iri} da:hasEnrollment ?enrollment .
            ?enrollment da:forCourse ?course ;
                        da:passed true .
            ?course da:courseCode ?code .
        }}
        """
    )
    return sorted(str(row["code"]) for row in rows)


def get_next_eligible_courses(student: str) -> list[str]:
    """List the course codes a student can take next.

    A course is eligible when the student has not passed it and every direct
    prerequisite has been passed.
    """
    iri = _student_iri(student)
    rows = _rows(
        f"""
        SELECT DISTINCT ?code WHERE {{
            ?course a/rdfs:subClassOf* da:Course ;
                    da:courseCode ?code .
            FILTER NOT EXISTS {{
                da:{iri} da:hasEnrollment ?passedEnrollment .
                ?passedEnrollment da:forCourse ?course ;
                                  da:passed true .
            }}
            FILTER NOT EXISTS {{
                ?course da:hasPrerequisite ?prerequisite .
                FILTER NOT EXISTS {{
                    da:{iri} da:hasEnrollment ?prerequisiteEnrollment .
                    ?prerequisiteEnrollment da:forCourse ?prerequisite ;
                                            da:passed true .
                }}
            }}
        }}
        """
    )
    return sorted(str(row["code"]) for row in rows)


def get_prerequisite_chain(course_code: str) -> list[str]:
    """Return every direct and indirect prerequisite of a course.

    For example get_prerequisite_chain("ML402") returns AI401, LA201, DS301,
    OOP201, PF101 and MATH101.
    """
    iri = _course_iri(course_code)
    rows = _rows(
        f"""
        SELECT DISTINCT ?code WHERE {{
            da:{iri} da:hasPrerequisite+ ?prerequisite .
            ?prerequisite da:courseCode ?code .
        }}
        """
    )
    return sorted(str(row["code"]) for row in rows)


def get_credits_remaining(student: str) -> int:
    """Return how many credits a student still needs to reach the program requirement."""
    iri = _student_iri(student)
    rows = _rows(
        f"""
        SELECT (IF(?required > ?earned, ?required - ?earned, 0) AS ?remaining) WHERE {{
            da:{iri} da:totalCreditsEarned ?earned ;
                      da:enrolledInProgram ?program .
            ?program da:minCreditsToGraduate ?required .
        }}
        LIMIT 1
        """
    )
    if not rows:
        return 0
    return int(rows[0]["remaining"])


def get_standing(student: str) -> str:
    """Return the academic standing for a student.

    One of: Probation, At Risk, Dean's List, Graduation Eligible, Good Standing.
    """
    iri = _student_iri(student)
    rows = _rows(
        f"""
        SELECT ?cgpa ?credits WHERE {{
            da:{iri} da:cgpa ?cgpa ;
                      da:totalCreditsEarned ?credits .
        }}
        LIMIT 1
        """
    )
    if not rows:
        return "Unknown"
    return _standing_label(float(rows[0]["cgpa"]), int(rows[0]["credits"]))


def get_courses_to_retake(student: str) -> list[str]:
    """List the course codes a student failed and must retake."""
    iri = _student_iri(student)
    rows = _rows(
        f"""
        SELECT DISTINCT ?code WHERE {{
            da:{iri} da:hasEnrollment ?enrollment .
            ?enrollment da:forCourse ?course ;
                        da:passed false .
            ?course da:courseCode ?code .
        }}
        """
    )
    return sorted(str(row["code"]) for row in rows)


############################################################
# Helpers for the Streamlit pages
############################################################


def list_students() -> list[dict[str, Any]]:
    """Return all students with their identifier and student ID."""
    rows = _rows(
        """
        SELECT ?student ?name ?studentId WHERE {
            ?student a da:Student .
            OPTIONAL { ?student da:fullName ?name }
            OPTIONAL { ?student da:studentId ?studentId }
        }
        """
    )
    students = []
    for row in rows:
        students.append(
            {
                "id": row["student"],
                "name": str(row["name"])
                if row["name"]
                else row["student"].removeprefix("Student_"),
                "studentId": str(row["studentId"]) if row["studentId"] else "",
            }
        )
    return sorted(students, key=lambda student: (student["studentId"], student["id"]))


def get_program_info() -> dict[str, Any]:
    """Return the degree program, its graduation thresholds and department."""
    rows = _rows(
        """
        SELECT ?program ?label ?minCredits ?minCgpa WHERE {
            ?program a da:Program ;
                     da:minCreditsToGraduate ?minCredits ;
                     da:minCgpaToGraduate ?minCgpa .
            OPTIONAL { ?program rdfs:label ?label }
        }
        LIMIT 1
        """
    )
    if not rows:
        return {}
    row = rows[0]
    return {
        "id": row["program"],
        "name": str(row["label"])
        if row["label"]
        else row["program"].removeprefix("Program_"),
        "minCreditsToGraduate": int(row["minCredits"]),
        "minCgpaToGraduate": float(row["minCgpa"]),
    }


def list_semesters() -> list[str]:
    """Return the teaching terms defined in the ontology."""
    rows = _rows(
        """
        SELECT ?name WHERE {
            ?semester a da:Semester ;
                      da:semesterName ?name .
        }
        """
    )
    return sorted(str(row["name"]) for row in rows)


def get_student_courses(student: str) -> list[dict[str, Any]]:
    """Return every enrollment of a student with course, grade, term and status."""
    iri = _student_iri(student)
    rows = _rows(
        f"""
        SELECT ?code ?title ?credits ?grade ?semester ?passed WHERE {{
            da:{iri} da:hasEnrollment ?enrollment .
            ?enrollment da:forCourse ?course ;
                        da:inSemester ?semesterNode ;
                        da:letterGrade ?grade ;
                        da:passed ?passed .
            ?course da:courseCode ?code ;
                    da:courseTitle ?title ;
                    da:creditHours ?credits .
            ?semesterNode da:semesterName ?semester .
        }}
        """
    )
    courses = []
    for row in rows:
        courses.append(
            {
                "code": str(row["code"]),
                "title": str(row["title"]),
                "credits": int(row["credits"]),
                "grade": str(row["grade"]),
                "semester": str(row["semester"]),
                "passed": bool(row["passed"]),
            }
        )
    return sorted(courses, key=lambda course: (course["semester"], course["code"]))


def get_course_catalog() -> list[dict[str, Any]]:
    """Return every course with title, credits, kind and direct prerequisites."""
    rows = _rows(
        """
        SELECT ?course ?code ?title ?credits ?kind WHERE {
            ?course a ?kind .
            ?kind rdfs:subClassOf* da:Course .
            ?course da:courseCode ?code ;
                    da:courseTitle ?title ;
                    da:creditHours ?credits .
        }
        """
    )
    prerequisite_rows = _rows(
        """
        SELECT ?course ?prerequisiteCode WHERE {
            ?course da:hasPrerequisite ?prerequisite .
            ?prerequisite da:courseCode ?prerequisiteCode .
        }
        """
    )
    prerequisites: dict[str, list[str]] = {}
    for row in prerequisite_rows:
        prerequisites.setdefault(row["course"], []).append(str(row["prerequisiteCode"]))

    catalog = []
    for row in rows:
        catalog.append(
            {
                "id": row["course"],
                "code": str(row["code"]),
                "title": str(row["title"]),
                "credits": int(row["credits"]),
                "kind": str(row["kind"]),
                "prerequisites": sorted(prerequisites.get(row["course"], [])),
            }
        )
    return sorted(catalog, key=lambda course: course["code"])


def get_prerequisite_edges() -> list[dict[str, str]]:
    """Return direct prerequisite edges (prerequisite to course) for the graph."""
    rows = _rows(
        """
        SELECT ?prerequisiteCode ?courseCode WHERE {
            ?course da:hasPrerequisite ?prerequisite ;
                    da:courseCode ?courseCode .
            ?prerequisite da:courseCode ?prerequisiteCode .
        }
        """
    )
    return [
        {"from": str(row["prerequisiteCode"]), "to": str(row["courseCode"])}
        for row in rows
    ]


def get_student_course_status(student: str) -> dict[str, set[str]]:
    """Return the passed and failed course codes for a student."""
    iri = _student_iri(student)
    rows = _rows(
        f"""
        SELECT ?code ?passed WHERE {{
            da:{iri} da:hasEnrollment ?enrollment .
            ?enrollment da:forCourse ?course ;
                        da:passed ?passed .
            ?course da:courseCode ?code .
        }}
        """
    )
    passed: set[str] = set()
    failed: set[str] = set()
    for row in rows:
        if bool(row["passed"]):
            passed.add(str(row["code"]))
        else:
            failed.add(str(row["code"]))
    return {"passed": passed, "failed": failed - passed}


def get_blocking_prerequisites(student: str, course_code: str) -> list[str]:
    """Return the direct prerequisites a student has not passed yet."""
    iri = _student_iri(student)
    course_iri = _course_iri(course_code)
    rows = _rows(
        f"""
        SELECT DISTINCT ?code WHERE {{
            da:{course_iri} da:hasPrerequisite ?prerequisite .
            ?prerequisite da:courseCode ?code .
            FILTER NOT EXISTS {{
                da:{iri} da:hasEnrollment ?enrollment .
                ?enrollment da:forCourse ?prerequisite ;
                            da:passed true .
            }}
        }}
        """
    )
    return sorted(str(row["code"]) for row in rows)


def get_probation_students() -> list[dict[str, Any]]:
    """Return every student below the probation CGPA threshold."""
    rows = _rows(
        f"""
        SELECT ?student ?name ?cgpa ?advisor ?advisorName WHERE {{
            ?student a da:Student ;
                     da:cgpa ?cgpa .
            FILTER(?cgpa < {PROBATION_CGPA})
            OPTIONAL {{ ?student da:fullName ?name }}
            OPTIONAL {{
                ?student da:hasAdvisor ?advisor .
                OPTIONAL {{ ?advisor da:fullName ?advisorName }}
            }}
        }}
        """
    )
    students = []
    for row in rows:
        advisor = row["advisor"] or ""
        students.append(
            {
                "id": row["student"],
                "name": str(row["name"])
                if row["name"]
                else row["student"].removeprefix("Student_"),
                "cgpa": round(float(row["cgpa"]), 2),
                "advisor": str(row["advisorName"])
                if row["advisorName"]
                else advisor.removeprefix("Advisor_"),
            }
        )
    return sorted(students, key=lambda student: student["name"])


def get_probation_count_by_advisor() -> list[dict[str, Any]]:
    """Return how many probation students each advisor has (CQ7)."""
    rows = _rows(
        f"""
        SELECT ?advisor ?advisorName (COUNT(?student) AS ?count) WHERE {{
            ?student da:cgpa ?cgpa ;
                     da:hasAdvisor ?advisor .
            FILTER(?cgpa < {PROBATION_CGPA})
            OPTIONAL {{ ?advisor da:fullName ?advisorName }}
        }}
        GROUP BY ?advisor ?advisorName
        ORDER BY DESC(?count)
        """
    )
    counts = []
    for row in rows:
        advisor = row["advisor"] or ""
        counts.append(
            {
                "advisor": str(row["advisorName"])
                if row["advisorName"]
                else advisor.removeprefix("Advisor_"),
                "count": int(row["count"]),
            }
        )
    return counts


def get_ontology_metrics() -> dict[str, int]:
    """Return measured counts from the loaded ontology graph."""
    def count(query: str) -> int:
        rows = _rows(query)
        return int(next(iter(rows[0].values()))) if rows else 0

    return {
        "classes": count(
            "SELECT (COUNT(DISTINCT ?x) AS ?n) WHERE { ?x a owl:Class . FILTER(isIRI(?x)) }"
        ),
        "objectProperties": count(
            "SELECT (COUNT(DISTINCT ?x) AS ?n) WHERE { ?x a owl:ObjectProperty }"
        ),
        "dataProperties": count(
            "SELECT (COUNT(DISTINCT ?x) AS ?n) WHERE { ?x a owl:DatatypeProperty }"
        ),
        "individuals": count(
            "SELECT (COUNT(DISTINCT ?x) AS ?n) WHERE { ?x a owl:NamedIndividual }"
        ),
        "triples": len(_graph()),
    }


def get_class_rows() -> list[dict[str, str]]:
    """Return classes with their direct parent and whether they are defined."""
    rows = _rows(
        """
        SELECT ?class ?parent WHERE {
            ?class a owl:Class .
            FILTER(isIRI(?class))
            OPTIONAL {
                ?class rdfs:subClassOf ?parent .
                FILTER(isIRI(?parent))
            }
        }
        """
    )
    defined_rows = _rows(
        "SELECT DISTINCT ?class WHERE { ?class owl:equivalentClass ?expression }"
    )
    defined = {row["class"] for row in defined_rows}
    classes = []
    for row in rows:
        classes.append(
            {
                "class": row["class"],
                "parent": row["parent"] or "owl:Thing",
                "defined": "yes" if row["class"] in defined else "no",
            }
        )
    return sorted(classes, key=lambda item: item["class"])


def get_property_rows() -> list[dict[str, str]]:
    """Return object and data properties with domain and range."""
    rows = _rows(
        """
        SELECT ?property ?type ?domain ?range WHERE {
            VALUES ?type { owl:ObjectProperty owl:DatatypeProperty }
            ?property a ?type .
            OPTIONAL { ?property rdfs:domain ?domain }
            OPTIONAL { ?property rdfs:range ?range }
        }
        """
    )
    properties = []
    for row in rows:
        properties.append(
            {
                "property": row["property"],
                "kind": "Object" if row["type"] == "ObjectProperty" else "Data",
                "domain": _display(row["domain"]),
                "range": _display(row["range"]),
            }
        )
    return sorted(
        properties,
        key=lambda item: (0 if item["kind"] == "Object" else 1, item["property"]),
    )


############################################################
# Competency questions (CQ1-CQ8)
############################################################

COMPETENCY_QUESTIONS: list[dict[str, str]] = [
    {
        "id": "CQ1",
        "question": "What are all direct and indirect prerequisites of ML402?",
        "expected": "AI401, LA201, DS301, OOP201, PF101, MATH101",
        "query": """SELECT DISTINCT ?p WHERE {
    da:ML402 da:hasPrerequisite+ ?p .
}
ORDER BY ?p""",
    },
    {
        "id": "CQ2",
        "question": "Which courses has Ayesha passed?",
        "expected": "PF101, OOP201, DS301, MATH101",
        "query": """SELECT DISTINCT ?course WHERE {
    da:Student_Ayesha da:hasEnrollment ?e .
    ?e da:forCourse ?course ;
       da:passed true .
}
ORDER BY ?course""",
    },
    {
        "id": "CQ3",
        "question": "Which courses can Ayesha take next?",
        "expected": "DB301, AI401, LA201, ETH101",
        "query": """SELECT DISTINCT ?c WHERE {
    ?c a/rdfs:subClassOf* da:Course .
    FILTER NOT EXISTS {
        da:Student_Ayesha da:hasEnrollment ?e0 .
        ?e0 da:forCourse ?c ;
            da:passed true .
    }
    FILTER NOT EXISTS {
        ?c da:hasPrerequisite ?p .
        FILTER NOT EXISTS {
            da:Student_Ayesha da:hasEnrollment ?e .
            ?e da:forCourse ?p ;
               da:passed true .
        }
    }
}
ORDER BY ?c""",
    },
    {
        "id": "CQ4",
        "question": "Which students have a CGPA below 2.0 (probation)?",
        "expected": "Student_Bilal (1.8)",
        "query": """SELECT ?s ?cgpa WHERE {
    ?s a da:Student ;
       da:cgpa ?cgpa .
    FILTER(?cgpa < 2.0)
}""",
    },
    {
        "id": "CQ5",
        "question": "How many credits does each student still need?",
        "expected": "Ayesha 34, Bilal 70, Hina 10, Zain 0, Maryam 100",
        "query": """SELECT ?s (IF(?min > ?c, ?min - ?c, 0) AS ?creditsRemaining) WHERE {
    ?s a da:Student ;
       da:totalCreditsEarned ?c ;
       da:enrolledInProgram ?p .
    ?p da:minCreditsToGraduate ?min .
}""",
    },
    {
        "id": "CQ6",
        "question": "Which students failed which courses?",
        "expected": "Bilal: PF101; Hina: DS301",
        "query": """SELECT ?s ?course WHERE {
    ?s da:hasEnrollment ?e .
    ?e da:passed false ;
       da:forCourse ?course .
}""",
    },
    {
        "id": "CQ7",
        "question": "How many probation students does each advisor have?",
        "expected": "Advisor_Khan: 1",
        "query": """SELECT ?a (COUNT(?s) AS ?n) WHERE {
    ?s da:cgpa ?g ;
       da:hasAdvisor ?a .
    FILTER(?g < 2.0)
} GROUP BY ?a""",
    },
    {
        "id": "CQ8",
        "question": "Which courses unlock the most later courses?",
        "expected": "PF101 (6), then OOP201 (5)",
        "query": """SELECT ?p (COUNT(DISTINCT ?c) AS ?unlocks) WHERE {
    ?c da:hasPrerequisite+ ?p .
} GROUP BY ?p ORDER BY DESC(?unlocks)""",
    },
]


def run_competency_questions() -> list[dict[str, Any]]:
    """Run CQ1 to CQ8 and return their rows for display."""
    results = []
    for item in COMPETENCY_QUESTIONS:
        rows = _rows(item["query"])
        display_rows = []
        for row in rows:
            values = []
            for value in row.values():
                if isinstance(value, bool):
                    values.append("true" if value else "false")
                elif value is None:
                    values.append("")
                else:
                    values.append(str(value))
            display_rows.append(values)
        results.append(
            {
                **item,
                "columns": list(rows[0].keys()) if rows else [],
                "rows": display_rows,
            }
        )
    return results
