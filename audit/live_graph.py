"""Build an in-memory personalized RDF graph for the Ontology Explorer.

The base ontology remains unchanged. This overlay materializes the UCP catalog
and the student's own profile so the explorer can show live, personalized graph
counts and triples.
"""

from __future__ import annotations

import os
import re
from typing import Any

from rdflib import Graph, Literal, Namespace
from rdflib.namespace import OWL, RDF, RDFS, XSD

from audit import catalog, profile
from audit.config import ONTOLOGY_PATH

DA = Namespace("http://example.org/ontologies/degree-audit#")

# The base ontology is parsed once per session and reused for every personalized
# overlay graph, so Ontology Explorer does not re-parse degree_audit.owl/ttl on
# every rerun or chat turn.
_BASE_GRAPH: Graph | None = None
_BASE_GRAPH_MTIME: float | None = None


def _load_base_graph() -> Graph:
    global _BASE_GRAPH, _BASE_GRAPH_MTIME
    mtime = os.path.getmtime(ONTOLOGY_PATH) if ONTOLOGY_PATH.exists() else None
    if _BASE_GRAPH is not None and _BASE_GRAPH_MTIME == mtime:
        return _BASE_GRAPH
    graph = Graph()
    graph.parse(str(ONTOLOGY_PATH), format="turtle")
    _BASE_GRAPH = graph
    _BASE_GRAPH_MTIME = mtime
    return _BASE_GRAPH


def _iri(text: str) -> str:
    return re.sub(r"[^A-Za-z0-9_]", "_", str(text))


def build_graph(profile_data: dict[str, Any] | None = None) -> Graph:
    profile_data = profile_data or profile.load_profile()
    base = _load_base_graph()
    try:
        graph = base.copy()
    except Exception:
        graph = Graph()
        for triple in base:
            graph.add(triple)

    department = DA["Dept_ComputerScience"]
    graph.set((department, RDF.type, DA.Department))
    graph.set((department, RDFS.label, Literal("Faculty of IT and Computer Science")))

    for program in catalog.list_programs():
        iri = DA[f"Program_{program['code']}"]
        graph.set((iri, RDF.type, DA.Program))
        graph.set((iri, RDFS.label, Literal(program["name"])))
        graph.set((iri, DA.minCreditsToGraduate, Literal(program["credits"], datatype=XSD.integer)))
        graph.set((iri, DA.minCgpaToGraduate, Literal("2.0", datatype=XSD.decimal)))
        graph.set((iri, DA.managedBy, department))

    for course in catalog.all_courses():
        iri = DA[_iri(course["code"])]
        category = course["category"].lower()
        kind = (
            DA.ElectiveCourse
            if "elective" in category or "general education" in category
            else DA.CoreCourse
        )
        graph.set((iri, RDF.type, kind))
        graph.set((iri, RDFS.label, Literal(course["title"])))
        graph.set((iri, DA.courseCode, Literal(course["code"])))
        graph.set((iri, DA.courseTitle, Literal(course["title"])))
        graph.set((iri, DA.creditHours, Literal(course["credits"], datatype=XSD.integer)))
        graph.set((iri, DA.offeredBy, department))
        for prerequisite in course["prerequisites"]:
            graph.add((iri, DA.hasPrerequisite, DA[_iri(prerequisite)]))
        for program_code in course["programs"]:
            graph.add((DA[f"Program_{program_code}"], DA.includesCourse, iri))

    summary = profile.summary(profile_data)
    has_user = bool(
        profile_data.get("name")
        or profile_data.get("roll_number")
        or profile_data.get("courses")
        or profile_data.get("planned_courses")
    )
    if not has_user:
        return graph

    user = DA.Student_MyProfile
    graph.add((user, RDF.type, DA.Student))
    graph.add((user, RDFS.label, Literal(profile_data.get("name") or "My profile")))
    graph.add((user, DA.fullName, Literal(profile_data.get("name") or "My profile")))
    graph.add((user, DA.studentId, Literal(profile_data.get("roll_number") or "LOCAL")))
    graph.add((user, DA.cgpa, Literal(str(profile_data["cgpa"]), datatype=XSD.decimal)))
    graph.add(
        (
            user,
            DA.totalCreditsEarned,
            Literal(summary["creditsPassed"], datatype=XSD.integer),
        )
    )
    graph.add((user, DA.enrolledInProgram, DA[f"Program_{profile_data['program']}"]))

    for record in profile_data["courses"]:
        enrollment = DA[f"Enr_My_{_iri(record['code'])}"]
        course = DA[_iri(record["code"])]
        semester = DA[f"Sem_My_{_iri(record['semester'])}"]
        graph.add((user, DA.hasEnrollment, enrollment))
        graph.add((enrollment, RDF.type, DA.Enrollment))
        graph.add((enrollment, DA.enrollmentOf, user))
        graph.add((enrollment, DA.forCourse, course))
        graph.add((enrollment, DA.inSemester, semester))
        graph.add((enrollment, DA.letterGrade, Literal(record["grade"])))
        graph.add((enrollment, DA.passed, Literal(bool(record["passed"]), datatype=XSD.boolean)))
        graph.add((semester, RDF.type, DA.Semester))
        graph.add((semester, DA.semesterName, Literal(record["semester"])))
        if record["counts_credits"]:
            graph.add((user, DA.hasCompleted, course))
        if record["grade"] in catalog.GRADE_POINTS and not record["counts_credits"]:
            graph.add((user, DA.mustRetake, course))

    return graph


def _local(term: Any) -> str:
    text = str(term)
    if "#" in text:
        return text.rsplit("#", 1)[-1]
    return text.rstrip("/").rsplit("/", 1)[-1]


def metrics(graph: Graph | None = None) -> dict[str, int]:
    graph = graph or build_graph()
    return {
        "classes": len(set(graph.subjects(RDF.type, OWL.Class))),
        "objectProperties": len(set(graph.subjects(RDF.type, OWL.ObjectProperty))),
        "dataProperties": len(set(graph.subjects(RDF.type, OWL.DatatypeProperty))),
        "individuals": len(set(graph.subjects(RDF.type, OWL.NamedIndividual))),
        "triples": len(graph),
        "catalogCourses": len(catalog.all_courses()),
        "catalogPrograms": len(catalog.list_programs()),
        "prerequisiteEdges": len(catalog.prerequisite_edges()),
    }


def user_triples(profile_data: dict[str, Any] | None = None) -> list[dict[str, str]]:
    graph = build_graph(profile_data)
    rows = []
    for subject, predicate, obj in graph:
        subject_name = _local(subject)
        if not (
            subject_name == "Student_MyProfile"
            or subject_name.startswith("Enr_My_")
            or subject_name.startswith("Sem_My_")
        ):
            continue
        rows.append(
            {
                "Subject": subject_name,
                "Predicate": _local(predicate),
                "Object": _local(obj) if not isinstance(obj, Literal) else str(obj),
            }
        )
    return sorted(rows, key=lambda row: (row["Subject"], row["Predicate"], row["Object"]))
