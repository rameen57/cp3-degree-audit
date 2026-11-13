"""Degreely - University Degree Audit front end.

Run from the project root:
    streamlit run app/app.py
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import html as html_lib

import pandas as pd
import streamlit as st

from agent.agent import ask
from audit import queries
from audit.config import llm_ready

APP_DIR = Path(__file__).resolve().parent

st.set_page_config(
    page_title="Degreely - Degree Audit",
    page_icon=":material/school:",
    layout="wide",
    initial_sidebar_state="expanded",
)

PAGES = [
    "Overview",
    "My Courses",
    "Course Planner",
    "Prerequisite Map",
    "Standing and Alerts",
    "Ask the Agent",
    "Ontology Explorer",
]


def load_css() -> None:
    css = (APP_DIR / "style.css").read_text(encoding="utf-8")
    st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)


def esc(value) -> str:
    return html_lib.escape(str(value))


def section_head(number: str, title: str) -> str:
    return (
        '<div class="section-head">'
        f'<span class="section-badge">{esc(number)}</span>'
        f"<span>{esc(title)}</span></div>"
    )


def page_header(title: str, subtitle: str) -> None:
    st.markdown(
        f'<div class="page-title">{esc(title)}</div>'
        f'<div class="page-sub">{esc(subtitle)}</div>',
        unsafe_allow_html=True,
    )


def logo_block() -> str:
    return """
    <div class="logo-block">
      <div class="logo-tile">D</div>
      <div>
        <div class="logo-name">Degreely</div>
        <div class="logo-tag">Level up your degree</div>
      </div>
    </div>
    """


def hero(name: str, program: str) -> str:
    return f"""
    <div class="hero">
      <div class="hero-tile">D</div>
      <div>
        <div class="hero-kicker">Player one</div>
        <h1>Welcome, {esc(name)}</h1>
        <p>{esc(program)} &middot; Keep your degree mission on track.</p>
      </div>
    </div>
    """


def standing_pill(standing: str) -> str:
    mapping = {
        "Probation": "pill-red",
        "At Risk": "pill-yellow",
        "Dean's List": "pill-green",
        "Graduation Eligible": "pill-green",
        "Good Standing": "pill-blue",
    }
    return mapping.get(standing, "pill-blue")


def status_card(standing: str, remaining: int, name: str) -> str:
    return f"""
    <div class="status-card">
      <div class="status-top">
        <div class="status-icon">▲</div>
        <div>
          <div class="status-caption">Current standing</div>
          <div class="status-value">{esc(standing)}</div>
        </div>
      </div>
      <div class="status-sub">{esc(name)} &middot; {remaining} credits remaining</div>
    </div>
    """


def metric_card(caption: str, value, sub: str, icon: str, compact: bool = False) -> str:
    value_class = "metric-value compact" if compact else "metric-value"
    return f"""
    <div class="metric-card">
      <div class="metric-icon">{esc(icon)}</div>
      <div class="metric-caption">{esc(caption)}</div>
      <div class="{value_class}">{esc(value)}</div>
      <div class="metric-sub">{esc(sub)}</div>
    </div>
    """


def alert(kind: str, title: str, text: str) -> str:
    return (
        f'<div class="alert alert-{kind}"><div>'
        f'<div class="alert-title">{esc(title)}</div>'
        f'<div class="alert-text">{esc(text)}</div>'
        "</div></div>"
    )


def empty_state(title: str, text: str) -> str:
    return (
        '<div class="empty">'
        f'<div class="empty-title">{esc(title)}</div>'
        f"<div>{esc(text)}</div>"
        "</div>"
    )


def course_table(courses: list[dict]) -> str:
    rows = []
    for course in courses:
        status = (
            '<span class="pill pill-green">Passed</span>'
            if course["passed"]
            else '<span class="pill pill-red">Failed</span>'
        )
        rows.append(
            "<tr>"
            f'<td><span class="course-code">{esc(course["code"])}</span></td>'
            f"<td>{esc(course['title'])}</td>"
            f"<td>{esc(course['grade'])}</td>"
            f"<td>{esc(course['semester'])}</td>"
            f"<td>{course['credits']}</td>"
            f"<td>{status}</td>"
            "</tr>"
        )
    return (
        '<table class="da-table"><thead><tr>'
        "<th>Code</th><th>Course</th><th>Grade</th><th>Semester</th>"
        "<th>Credits</th><th>Status</th>"
        "</tr></thead><tbody>"
        + "".join(rows)
        + "</tbody></table>"
    )


def course_card(course: dict) -> str:
    kind = "Elective" if "Elective" in course.get("kind", "") else "Core"
    prerequisites = ", ".join(course.get("prerequisites", [])) or "None"
    return f"""
    <div class="course-card">
      <div class="course-top">
        <span class="course-code">{esc(course.get("code", ""))}</span>
        <span class="pill pill-blue">{esc(kind)}</span>
      </div>
      <div class="course-title">{esc(course.get("title", ""))}</div>
      <div class="course-meta">{course.get("credits", 0)} credit hours</div>
      <div class="course-meta">Prerequisites: {esc(prerequisites)}</div>
    </div>
    """


def chips(items: list[str], empty_text: str) -> str:
    if not items:
        return f'<span class="course-meta">{esc(empty_text)}</span>'
    return " ".join(
        f'<span class="pill pill-blue">{esc(item)}</span>' for item in items
    )


def render_overview(student_id: str, student_name: str, program: dict, semesters: list[str]) -> None:
    summary = queries.get_student_summary(student_id)
    remaining = queries.get_credits_remaining(student_id)
    program_name = program.get("name", "Degree program")

    st.markdown(hero(summary.get("name", student_name), program_name), unsafe_allow_html=True)

    with st.container(border=True):
        st.markdown('<div class="form-title">Player profile</div>', unsafe_allow_html=True)
        first, second, third = st.columns([1.2, 1.4, 1.2])
        with first:
            chosen = st.selectbox(
                "Student",
                [student["name"] for student in students],
                index=[student["name"] for student in students].index(student_name),
                key="overview_student",
            )
        with second:
            st.selectbox("Program", [program_name], key="overview_program")
        with third:
            st.selectbox(
                "Semester",
                semesters or ["Fall 2025"],
                key="overview_semester",
            )
        st.caption("Choose a player, then press Load student to switch every mission.")
        if st.button("Load student", type="primary", key="load_student"):
            st.session_state.student_name = chosen
            st.toast(f"Loaded {chosen}.")
            st.rerun()

    st.write("")
    columns = st.columns(4)
    with columns[0]:
        st.markdown(
            metric_card("CGPA", f"{summary.get('cgpa', 0):.2f}", "on a 4.0 scale", "◎"),
            unsafe_allow_html=True,
        )
    with columns[1]:
        st.markdown(
            metric_card(
                "Credits earned",
                summary.get("totalCreditsEarned", 0),
                f"of {program.get('minCreditsToGraduate', 0)} required",
                "▤",
            ),
            unsafe_allow_html=True,
        )
    with columns[2]:
        st.markdown(
            metric_card("Credits remaining", remaining, "to graduation", "➜"),
            unsafe_allow_html=True,
        )
    with columns[3]:
        st.markdown(
            metric_card(
                "Standing",
                summary.get("standing", "Unknown"),
                f"Advisor {summary.get('advisorName', 'not assigned')}",
                "★",
                compact=True,
            ),
            unsafe_allow_html=True,
        )


def render_courses(student_id: str, student_name: str) -> None:
    page_header("My Courses", f"Passed courses, grades and retakes for {student_name}.")
    courses = queries.get_student_courses(student_id)
    passed = [course for course in courses if course["passed"]]
    failed = [course for course in courses if not course["passed"]]
    credits_passed = sum(course["credits"] for course in passed)

    columns = st.columns(3)
    with columns[0]:
        st.markdown(
            metric_card("Courses passed", len(passed), "on the record", "▤"),
            unsafe_allow_html=True,
        )
    with columns[1]:
        st.markdown(
            metric_card("Credits passed", credits_passed, "from passed courses", "◎"),
            unsafe_allow_html=True,
        )
    with columns[2]:
        st.markdown(
            metric_card("Retakes flagged", len(failed), "failed courses", "↺"),
            unsafe_allow_html=True,
        )

    st.markdown('<div class="section-title">Passed courses</div>', unsafe_allow_html=True)
    if passed:
        st.markdown(course_table(passed), unsafe_allow_html=True)
    else:
        st.markdown(
            empty_state(
                "No passed courses yet",
                "This player has no passing enrollments in the ontology.",
            ),
            unsafe_allow_html=True,
        )

    st.markdown('<div class="section-title">Retakes</div>', unsafe_allow_html=True)
    if failed:
        for course in failed:
            st.markdown(
                alert(
                    "red",
                    f"Retake required: {course['code']}",
                    f"{course['title']} was failed with grade {course['grade']} in "
                    f"{course['semester']}. Schedule the retake with an advisor.",
                ),
                unsafe_allow_html=True,
            )
    else:
        st.markdown(
            alert("green", "All clear", "No failed courses on this player's record."),
            unsafe_allow_html=True,
        )


def render_planner(student_id: str, student_name: str) -> None:
    page_header("Course Planner", f"Pick the next course for {student_name} and see what blocks it.")
    catalog = queries.get_course_catalog()
    by_code = {course["code"]: course for course in catalog}
    eligible = queries.get_next_eligible_courses(student_id)

    st.markdown('<div class="section-title">Ready to take next</div>', unsafe_allow_html=True)
    if eligible:
        columns = st.columns(3)
        for index, code in enumerate(eligible):
            with columns[index % 3]:
                st.markdown(
                    course_card(by_code.get(code, {"code": code, "title": code})),
                    unsafe_allow_html=True,
                )
    else:
        st.markdown(
            empty_state(
                "Nothing is unlocked right now",
                "Pass the current prerequisites or check the retake list.",
            ),
            unsafe_allow_html=True,
        )

    st.markdown('<div class="section-title">Course picker</div>', unsafe_allow_html=True)
    options = {
        f"{course['code']} - {course['title']}": course for course in catalog
    }
    if not options:
        st.markdown(
            empty_state("No courses found", "The ontology has no course individuals."),
            unsafe_allow_html=True,
        )
        return
    label = st.selectbox("Course", list(options.keys()), key="planner_course")
    course = options[label]
    code = course["code"]
    status = queries.get_student_course_status(student_id)
    chain = queries.get_prerequisite_chain(code)
    blocking = queries.get_blocking_prerequisites(student_id, code)

    if code in status["passed"]:
        st.markdown(
            alert("green", "Already completed", f"{code} is on this player's passed list."),
            unsafe_allow_html=True,
        )
    elif blocking:
        st.markdown(
            alert(
                "red",
                f"{code} is locked",
                f"Complete {', '.join(blocking)} first. Those direct prerequisites "
                "are not yet passed.",
            ),
            unsafe_allow_html=True,
        )
    elif code in status["failed"]:
        st.markdown(
            alert(
                "yellow",
                "Retake required",
                f"Prerequisites are satisfied. {code} is a retake; schedule it this term.",
            ),
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            alert("green", f"{code} is ready", "Every prerequisite is satisfied."),
            unsafe_allow_html=True,
        )

    details_left, details_right = st.columns([1, 2])
    with details_left:
        st.markdown(
            metric_card(
                f"{code}",
                f"{course['credits']} credits",
                "Elective" if "Elective" in course["kind"] else "Core course",
                "▤",
                compact=True,
            ),
            unsafe_allow_html=True,
        )
    with details_right:
        st.markdown("**Direct prerequisites**", unsafe_allow_html=False)
        st.markdown(chips(course["prerequisites"], "None - open to everyone."), unsafe_allow_html=True)
        st.markdown("**Full prerequisite chain**")
        st.markdown(chips(chain, "No prerequisites."), unsafe_allow_html=True)


def render_map(student_id: str, student_name: str) -> None:
    page_header("Prerequisite Map", f"Every course and prerequisite edge, coloured for {student_name}.")
    catalog = queries.get_course_catalog()
    status = queries.get_student_course_status(student_id)
    edges = queries.get_prerequisite_edges()

    legend_columns = st.columns(3)
    with legend_columns[0]:
        st.markdown(
            '<span class="pill pill-green">Passed</span>', unsafe_allow_html=True
        )
    with legend_columns[1]:
        st.markdown(
            '<span class="pill pill-red">Failed</span>', unsafe_allow_html=True
        )
    with legend_columns[2]:
        st.markdown(
            '<span class="pill pill-blue">Not started</span>', unsafe_allow_html=True
        )

    dot = [
        "digraph degree_audit {",
        'rankdir="LR";',
        'bgcolor="transparent";',
        'node [shape="box", style="rounded,filled", fontname="Poppins", '
        'fontsize="12", fontcolor="white", color="#9cc0ff", penwidth="1.4"];',
        'edge [color="#9cc0ff", arrowhead="vee", penwidth="1.4"];',
    ]
    for course in catalog:
        code = course["code"]
        if code in status["passed"]:
            fill = "#20a96b"
        elif code in status["failed"]:
            fill = "#d9534f"
        else:
            fill = "#53699f"
        title = str(course["title"]).replace('"', "'")
        dot.append(
            f'"{code}" [label="{code}\\n{title}", fillcolor="{fill}"];'
        )
    for edge in edges:
        dot.append(f'"{edge["from"]}" -> "{edge["to"]}";')
    dot.append("}")

    st.graphviz_chart("\n".join(dot), width="stretch")
    st.caption("Arrows point from a prerequisite to the course it unlocks.")


def render_standing(student_id: str, student_name: str) -> None:
    page_header("Standing and Alerts", "Academic standing and the advisor-meeting watchlist.")
    summary = queries.get_student_summary(student_id)
    standing = queries.get_standing(student_id)
    remaining = queries.get_credits_remaining(student_id)
    advisor = summary.get("advisorName", "not assigned")

    st.markdown(
        f"""
        <div class="standing-badge">
          <div class="standing-icon">★</div>
          <div>
            <div class="standing-label">Academic standing</div>
            <div class="standing-value">{esc(standing)}</div>
          </div>
          <div class="standing-side">
            <span class="pill {standing_pill(standing)}">{esc(standing)}</span>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    columns = st.columns(2)
    with columns[0]:
        st.markdown(
            metric_card("Advisor", advisor, "Assigned academic advisor", "▤", compact=True),
            unsafe_allow_html=True,
        )
    with columns[1]:
        st.markdown(
            metric_card("Credits remaining", remaining, "to graduation", "➜"),
            unsafe_allow_html=True,
        )

    if standing == "Probation":
        st.markdown(
            alert(
                "red",
                "Advisor meeting required",
                f"{student_name} is on probation (CGPA below 2.0). "
                f"Book a meeting with advisor {advisor}.",
            ),
            unsafe_allow_html=True,
        )
    elif standing == "At Risk":
        st.markdown(
            alert(
                "yellow",
                "Keep an eye on this one",
                f"{student_name} is at risk (CGPA between 2.0 and 2.5). "
                f"Advisor {advisor} can help plan the next term.",
            ),
            unsafe_allow_html=True,
        )
    elif standing == "Graduation Eligible":
        st.markdown(
            alert(
                "green",
                "Graduation eligible",
                "The credit and CGPA thresholds are met. Confirm the final audit "
                "with the department.",
            ),
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            alert(
                "green",
                "On track",
                f"{student_name} is in good standing. Keep the current plan moving.",
            ),
            unsafe_allow_html=True,
        )

    st.markdown('<div class="section-title">Probation watchlist</div>', unsafe_allow_html=True)
    counts = queries.get_probation_count_by_advisor()
    if counts:
        rows = "".join(
            f"<tr><td>{esc(item['advisor'])}</td><td>{item['count']}</td></tr>"
            for item in counts
        )
        st.markdown(
            '<table class="da-table"><thead><tr><th>Advisor</th>'
            "<th>Probation students</th></tr></thead><tbody>"
            + rows
            + "</tbody></table>",
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            empty_state("No probation alerts", "No student is below the 2.0 CGPA threshold."),
            unsafe_allow_html=True,
        )


def render_agent(student_id: str, student_name: str) -> None:
    page_header("Ask the Agent", "The Degree Audit Assistant answers only from ontology tool results.")
    st.markdown(
        f'<span class="pill pill-yellow">Auditing: {esc(student_name)}</span>',
        unsafe_allow_html=True,
    )

    if not llm_ready():
        st.markdown(
            alert(
                "yellow",
                "Gemini API key needed",
                "Every other page works without a key. To unlock the agent, copy "
                ".env.example to .env and paste a key from Google AI Studio, then "
                "restart the app.",
            ),
            unsafe_allow_html=True,
        )
        st.code("GEMINI_API_KEY=your_api_key_here", language="bash")
        return

    if st.session_state.chat:
        if st.button("Clear chat", key="clear_chat"):
            st.session_state.chat = []
            st.rerun()

    for message in st.session_state.chat:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
            if message["role"] == "assistant":
                tools = message.get("tools") or []
                st.caption("Tools used: " + (", ".join(tools) if tools else "none"))

    prompt = st.chat_input("Ask about courses, prerequisites, credits or standing...")
    if prompt:
        st.session_state.chat.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)
        with st.chat_message("assistant"):
            with st.spinner("Checking the ontology..."):
                result = ask(prompt, student_id)
            st.markdown(result["answer"])
            tools = result.get("tools_used", [])
            st.caption("Tools used: " + (", ".join(tools) if tools else "none"))
        st.session_state.chat.append(
            {
                "role": "assistant",
                "content": result["answer"],
                "tools": tools,
            }
        )


def render_explorer() -> None:
    page_header("Ontology Explorer", "The classes, properties and competency questions behind the app.")
    metrics = queries.get_ontology_metrics()

    columns = st.columns(4)
    with columns[0]:
        st.markdown(
            metric_card("Classes", metrics["classes"], "OWL classes", "▤"),
            unsafe_allow_html=True,
        )
    with columns[1]:
        st.markdown(
            metric_card("Object properties", metrics["objectProperties"], "relationships", "◎"),
            unsafe_allow_html=True,
        )
    with columns[2]:
        st.markdown(
            metric_card("Data properties", metrics["dataProperties"], "literal values", "▤"),
            unsafe_allow_html=True,
        )
    with columns[3]:
        st.markdown(
            metric_card("Individuals", metrics["individuals"], f"{metrics['triples']} graph triples", "★"),
            unsafe_allow_html=True,
        )

    class_tab, property_tab, cq_tab = st.tabs(
        ["Classes", "Properties", "Competency questions"]
    )

    with class_tab:
        classes = queries.get_class_rows()
        frame = pd.DataFrame(
            [
                {
                    "Class": item["class"],
                    "Parent": item["parent"],
                    "Defined (inferred)": item["defined"],
                }
                for item in classes
            ]
        )
        st.dataframe(frame, hide_index=True, width="stretch")

    with property_tab:
        properties = queries.get_property_rows()
        frame = pd.DataFrame(
            [
                {
                    "Property": item["property"],
                    "Kind": item["kind"],
                    "Domain": item["domain"],
                    "Range / type": item["range"],
                }
                for item in properties
            ]
        )
        st.dataframe(frame, hide_index=True, width="stretch")

    with cq_tab:
        if st.button("Run CQ1 - CQ8", type="primary", key="run_cq"):
            st.session_state.cq_results = queries.run_competency_questions()
        results = st.session_state.cq_results
        if not results:
            st.caption("Run the eight competency questions to see their live results.")
        else:
            for result in results:
                with st.expander(f"{result['id']} - {result['question']}"):
                    st.markdown(f"**Expected:** {result['expected']}")
                    st.code(result["query"], language="sparql")
                    if result["rows"]:
                        frame = pd.DataFrame(result["rows"], columns=result["columns"])
                        st.dataframe(frame, hide_index=True, width="stretch")
                    else:
                        st.info("No rows returned.")


load_css()

students = queries.list_students()
if not students:
    st.error("No students found in the ontology.")
    st.stop()

student_names = [student["name"] for student in students]
name_to_id = {student["name"]: student["id"] for student in students}
program = queries.get_program_info()
semesters = queries.list_semesters()

if "page" not in st.session_state:
    st.session_state.page = PAGES[0]
if "student_name" not in st.session_state or st.session_state.student_name not in student_names:
    st.session_state.student_name = student_names[0]
if "chat" not in st.session_state:
    st.session_state.chat = []
if "cq_results" not in st.session_state:
    st.session_state.cq_results = None

active_name = st.session_state.student_name
student_id = name_to_id[active_name]
summary = queries.get_student_summary(student_id)
remaining = queries.get_credits_remaining(student_id)

with st.sidebar:
    st.markdown(logo_block(), unsafe_allow_html=True)
    st.markdown(section_head("1", "Choose a mission"), unsafe_allow_html=True)
    for number, page in enumerate(PAGES, start=1):
        is_active = st.session_state.page == page
        if st.button(
            f"{number}   {page}",
            key=f"nav_{page}",
            use_container_width=True,
            type="primary" if is_active else "secondary",
        ):
            st.session_state.page = page
            st.rerun()

    st.markdown(section_head("2", "Mission status"), unsafe_allow_html=True)
    st.markdown(
        status_card(
            summary.get("standing", "Unknown"),
            remaining,
            summary.get("name", active_name),
        ),
        unsafe_allow_html=True,
    )

page = st.session_state.page

if page == "Overview":
    render_overview(student_id, active_name, program, semesters)
elif page == "My Courses":
    render_courses(student_id, active_name)
elif page == "Course Planner":
    render_planner(student_id, active_name)
elif page == "Prerequisite Map":
    render_map(student_id, active_name)
elif page == "Standing and Alerts":
    render_standing(student_id, active_name)
elif page == "Ask the Agent":
    render_agent(student_id, active_name)
elif page == "Ontology Explorer":
    render_explorer()

