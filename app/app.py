"""Degreely - Personalized UCP Degree Audit front end.

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

from agent import agent
from audit import catalog, profile, live_graph
from audit.config import llm_ready

APP_DIR = Path(__file__).resolve().parent

st.set_page_config(
    page_title="Degreely - UCP Degree Audit",
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
        <div class="logo-tag">Level up your UCP degree</div>
      </div>
    </div>
    """


def hero(name: str, program: str) -> str:
    return f"""
    <div class="hero">
      <div class="hero-tile">D</div>
      <div>
        <div class="hero-kicker">Player one</div>
        <h1>Welcome, {esc(name) or "Student"}</h1>
        <p>{esc(program)} &middot; Keep your UCP degree mission on track.</p>
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
    kind = "Elective" if "Elective" in course.get("category", "") else "Core"
    prerequisites = ", ".join(course.get("prerequisites", [])) or "None"
    return f"""
    <div class="course-card">
      <div class="course-top">
        <span class="course-code">{esc(course.get('code', ''))}</span>
        <span class="pill pill-blue">{esc(kind)}</span>
      </div>
      <div class="course-title">{esc(course.get('title', ''))}</div>
      <div class="course-meta">{course.get('credits', 0)} credit hours</div>
      <div class="course-meta">Programs: {esc(', '.join(course.get('programs', [])))}</div>
      <div class="course-meta">Prerequisites: {esc(prerequisites)}</div>
    </div>
    """


def chips(items: list[str], empty_text: str) -> str:
    if not items:
        return f'<span class="course-meta">{esc(empty_text)}</span>'
    return " ".join(
        f'<span class="pill pill-blue">{esc(item)}</span>' for item in items
    )


def course_label(course: dict) -> str:
    return f"{course['code']} - {course['title']}"


def code_from_label(label: str) -> str:
    return str(label or "").split(" - ")[0].strip().upper()


def save_profile(new_profile: dict) -> None:
    st.session_state.profile = profile.save_profile(new_profile)
    st.toast("Profile saved.")
    st.rerun()


def submit_prompt(text: str) -> None:
    st.session_state.chat.append({"role": "user", "content": text})
    with st.chat_message("user"):
        st.markdown(text)
    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            result = agent.ask(text, st.session_state.profile.get("name", ""))
        st.markdown(result["answer"])
        tools = result.get("tools_used", [])
        st.caption("Tools used: " + (", ".join(tools) if tools else "none"))
    st.session_state.chat.append(
        {"role": "assistant", "content": result["answer"], "tools": tools}
    )
    st.rerun()


def render_overview() -> None:
    profile_data = st.session_state.profile
    summary = profile.summary(profile_data)
    program = summary["program"]
    st.markdown(hero(profile_data.get("name", ""), program["name"]), unsafe_allow_html=True)

    with st.container(border=True):
        st.markdown('<div class="form-title">Student profile</div>', unsafe_allow_html=True)
        first, second, third = st.columns([1.4, 1.2, 1.2])
        with first:
            name = st.text_input("Name", profile_data.get("name", ""), key="profile_name")
        with second:
            roll = st.text_input("Roll number", profile_data.get("roll_number", ""), key="profile_roll")
        with third:
            program_names = catalog.program_names()
            current_name = catalog.program_name(profile_data.get("program", "BSCS"))
            if current_name not in program_names:
                program_names = [current_name] + program_names
            program_choice = st.selectbox(
                "Program",
                program_names,
                index=program_names.index(current_name),
                key="profile_program",
                accept_new_options=True,
            )
        semester_options = list(profile.DEFAULT_TERMS)
        if profile_data.get("semester") and profile_data["semester"] not in semester_options:
            semester_options.append(profile_data["semester"])
        semester = st.selectbox(
            "Semester",
            semester_options,
            index=semester_options.index(profile_data.get("semester", semester_options[0])),
            key="profile_semester",
            accept_new_options=True,
        )
        cgpa = st.number_input(
            "CGPA",
            0.0,
            4.0,
            float(profile_data.get("cgpa", 0.0)),
            0.01,
            key="profile_cgpa",
        )
        st.caption("Choose from UCP's five IT programs. Your profile is saved locally in data/my_profile.json.")
        if st.button("Save profile", type="primary", key="save_profile"):
            try:
                catalog.resolve_program(program_choice)
                save_profile(
                    {
                        "name": name,
                        "roll_number": roll,
                        "program": program_choice,
                        "semester": semester,
                        "cgpa": cgpa,
                        "courses": profile_data.get("courses", []),
                        "planned_courses": profile_data.get("planned_courses", []),
                    }
                )
            except ValueError as exc:
                st.error(str(exc))

    st.write("")
    columns = st.columns(4)
    with columns[0]:
        st.markdown(
            metric_card("CGPA", f"{profile_data.get('cgpa', 0):.2f}", "on a 4.0 scale", "◎"),
            unsafe_allow_html=True,
        )
    with columns[1]:
        st.markdown(
            metric_card(
                "Credits passed",
                summary["creditsPassed"],
                f"of {program['credits']} required",
                "▤",
            ),
            unsafe_allow_html=True,
        )
    with columns[2]:
        st.markdown(
            metric_card("Credits remaining", summary["creditsRemaining"], "to graduation", "➜"),
            unsafe_allow_html=True,
        )
    with columns[3]:
        st.markdown(
            metric_card(
                "Standing",
                summary["standing"],
                "Dean's List" if summary["deanList"] else "Check thresholds below",
                "★",
                compact=True,
            ),
            unsafe_allow_html=True,
        )

    st.progress(summary["progress"] / 100.0)
    st.caption(f"Program progress: {summary['creditsPassed']} / {program['credits']} credits ({summary['progress']}%).")

    if st.button("Compute CGPA from my entered courses", key="compute_cgpa"):
        estimated = catalog.estimate_cgpa(profile_data.get("courses", []))
        updated = dict(profile_data)
        updated["cgpa"] = estimated
        save_profile(updated)

    if not summary["hasProfile"]:
        st.markdown(
            alert(
                "yellow",
                "Complete your profile",
                "Enter your name, roll number, program, semester, and CGPA in Overview, then save it.",
            ),
            unsafe_allow_html=True,
        )


def render_courses() -> None:
    profile_data = st.session_state.profile
    summary = profile.summary(profile_data)
    page_header("My Courses", "Add verified UCP courses, grades, and terms for your personal audit.")

    st.markdown('<div class="section-title">Add or verify a course</div>', unsafe_allow_html=True)
    mode = st.radio(
        "Course source",
        ["UCP catalog", "Custom course"],
        horizontal=True,
        key="course_mode",
    )
    code = ""
    title = ""
    credits = 3
    prerequisites = []
    custom_programs = [profile_data.get("program", "BSCS")]

    if mode == "UCP catalog":
        show_all = st.checkbox("Show all UCP IT courses", value=False, key="show_all_courses")
        choices = catalog.all_courses(None if show_all else profile_data["program"])
        options = [course_label(course) for course in choices]
        label = st.selectbox(
            "Course",
            options,
            key="add_course_label",
            accept_new_options=True,
        )
        if label:
            code = code_from_label(label)
            course = catalog.get_course(code)
            if course:
                title = course["title"]
                credits = course["credits"]
                prerequisites = course["prerequisites"]
                custom_programs = course["programs"]
    else:
        code = st.text_input("Course code", key="custom_code").strip().upper()
        title = st.text_input("Course title", key="custom_title")
        credits = st.number_input("Credit hours", 1, 6, 3, key="custom_credits")
        prereq_text = st.text_input("Prerequisites (comma-separated codes)", key="custom_prereqs")
        prerequisites = [p.strip().upper() for p in prereq_text.split(",") if p.strip()]
        custom_programs = st.multiselect(
            "Programs",
            catalog.program_codes(),
            default=[profile_data.get("program", "BSCS")],
            key="custom_programs",
        )
        if st.button("Add custom course to UCP catalog", key="save_custom_course"):
            try:
                catalog.add_custom_course(code, title, int(credits), prerequisites, custom_programs)
                st.success(f"Added {code} to the local catalog.")
                st.rerun()
            except Exception as exc:
                st.error(str(exc))

    term_options = list(profile.DEFAULT_TERMS)
    if profile_data.get("semester") and profile_data["semester"] not in term_options:
        term_options.append(profile_data["semester"])
    grade = st.selectbox("Grade", catalog.GRADE_OPTIONS, key="add_grade")
    semester = st.selectbox(
        "Semester / term",
        term_options,
        index=term_options.index(profile_data.get("semester", term_options[0])),
        key="add_term",
        accept_new_options=True,
    )

    if st.button("Verify & add course", type="primary", key="add_course_btn"):
        if not code:
            st.error("Choose or type a course code.")
        elif mode == "Custom course" and not title:
            st.error("Custom courses need a title.")
        else:
            try:
                result = profile.add_course(code, grade, semester)
                st.session_state.last_add = result
                st.success(result["verification"]["message"])
                st.rerun()
            except Exception as exc:
                st.error(str(exc))

    last_add = st.session_state.get("last_add")
    if last_add:
        plan = last_add["plan"]
        st.markdown('<div class="section-title">Last addition</div>', unsafe_allow_html=True)
        st.markdown(
            f"**{plan['course']['code']} - {plan['course']['title']}**: {last_add['verification']['message']}"
        )
        st.markdown(
            alert(
                "green" if plan["state"] != "locked" else "red",
                plan["course"]["code"],
                plan["message"],
            ),
            unsafe_allow_html=True,
        )
        if plan["directMissing"]:
            st.markdown(
                f"Missing direct prerequisites: {chips(plan['directMissing'], 'none')}",
                unsafe_allow_html=True,
            )
        if plan["unlocks"]:
            st.markdown(
                f"Unlocks: {chips(plan['unlocks'][:12], 'none')}"
                + (f" and {len(plan['unlocks']) - 12} more." if len(plan["unlocks"]) > 12 else "."),
                unsafe_allow_html=True,
            )
        if st.button("Dismiss", key="dismiss_last_add"):
            st.session_state.last_add = None
            st.rerun()

    st.markdown('<div class="section-title">Your courses</div>', unsafe_allow_html=True)
    courses = summary["courses"]
    columns = st.columns(4)
    with columns[0]:
        st.markdown(
            metric_card("Courses recorded", len(courses), "on your profile", "▤"),
            unsafe_allow_html=True,
        )
    with columns[1]:
        st.markdown(
            metric_card("Passed", len(summary["passed"]), "credits count toward graduation", "◎"),
            unsafe_allow_html=True,
        )
    with columns[2]:
        st.markdown(
            metric_card("Failed", len(summary["failed"]), "must be retaken", "↺"),
            unsafe_allow_html=True,
        )
    with columns[3]:
        st.markdown(
            metric_card("In progress", len(summary["pending"]), "not yet graded", "○"),
            unsafe_allow_html=True,
        )

    if courses:
        st.markdown(course_table(courses), unsafe_allow_html=True)
        record_options = [course_label(course) for course in courses]
        remove_label = st.selectbox(
            "Remove a course",
            [""] + record_options,
            key="remove_course_label",
        )
        if st.button("Remove selected course", key="remove_course_btn"):
            if not remove_label:
                st.error("Choose a course to remove.")
            else:
                profile.remove_course(code_from_label(remove_label))
                st.rerun()
        if st.button("Clear all my courses", key="clear_courses_btn"):
            profile.clear_courses()
            st.rerun()
    else:
        st.markdown(
            empty_state(
                "No courses recorded yet",
                "Use the form above to add UCP courses from the catalog or a custom course.",
            ),
            unsafe_allow_html=True,
        )

    if summary["prerequisiteGaps"]:
        st.markdown('<div class="section-title">Prerequisite gaps in completed courses</div>', unsafe_allow_html=True)
        for gap in summary["prerequisiteGaps"]:
            st.markdown(
                alert(
                    "yellow",
                    f"{gap['code']} has unmet prerequisite(s)",
                    f"Complete {', '.join(gap['missing'])} before treating {gap['code']} as fully unlocked.",
                ),
                unsafe_allow_html=True,
            )


def render_planner() -> None:
    profile_data = st.session_state.profile
    page_header("Course Planner", "Search UCP IT courses, see prerequisites, and plan your next courses.")

    program_choice = st.selectbox(
        "Show courses for",
        ["All UCP IT courses"] + catalog.program_names(),
        index=0,
        key="planner_program",
        accept_new_options=True,
    )
    query = st.text_input("Search code or title", key="planner_search")
    program = None if program_choice == "All UCP IT courses" else program_choice
    choices = catalog.search_courses(query, program)
    options = [course_label(course) for course in choices]
    label = st.selectbox(
        "Course (type a code or choose from the dropdown)",
        options,
        key="planner_course_label",
        accept_new_options=True,
    )

    if label:
        code = code_from_label(label)
        course = catalog.get_course(code)
        if course is None:
            st.error(f"{code} is not in the UCP catalog. Add it as a custom course first, or choose a catalog course.")
        else:
            plan = profile.plan_course(code, profile_data)
            st.markdown(course_card(course), unsafe_allow_html=True)
            st.markdown(
                alert(
                    "green" if plan["state"] in ("completed", "ready") else ("red" if plan["state"] == "locked" else "blue"),
                    f"{course['code']} status",
                    plan["message"],
                ),
                unsafe_allow_html=True,
            )
            st.markdown("**Direct prerequisites**", unsafe_allow_html=False)
            st.markdown(chips(course["prerequisites"], "None - open to everyone."), unsafe_allow_html=True)
            st.markdown("**Full prerequisite chain**")
            st.markdown(chips(plan["fullChain"], "No prerequisites."), unsafe_allow_html=True)
            st.markdown("**This course unlocks**")
            st.markdown(chips(plan["unlocks"][:20], "No later courses found."), unsafe_allow_html=True)
            if not plan["inProgram"]:
                st.markdown(
                    alert(
                        "yellow",
                        "Outside your current program",
                        f"{course['code']} is not listed for {catalog.program_name(profile_data['program'])}; it can still count as an extra/elective if your department allows.",
                    ),
                    unsafe_allow_html=True,
                )
            col_plan, col_remove = st.columns(2)
            with col_plan:
                if st.button("Add to my plan", key="planner_add_plan"):
                    profile.add_planned(code, profile_data)
                    st.success(f"Added {code} to your plan.")
                    st.rerun()
            with col_remove:
                if st.button("Remove from my plan", key="planner_remove_plan"):
                    profile.remove_planned(code, profile_data)
                    st.success(f"Removed {code} from your plan.")
                    st.rerun()

    st.markdown('<div class="section-title">Ready to take next (your program)</div>', unsafe_allow_html=True)
    eligible = profile.eligible_courses(profile_data)
    if eligible:
        columns = st.columns(3)
        for index, course in enumerate(eligible):
            with columns[index % 3]:
                st.markdown(course_card(course), unsafe_allow_html=True)
    else:
        st.markdown(
            empty_state(
                "Nothing is unlocked right now",
                "Pass the prerequisites for your completed courses, or check retakes.",
            ),
            unsafe_allow_html=True,
        )

    st.markdown('<div class="section-title">Planned courses</div>', unsafe_allow_html=True)
    planned = summary["planned"] if (summary := profile.summary(profile_data)) else []
    if planned:
        planned_options = [course_label(course) for course in planned]
        remove_label = st.selectbox(
            "Remove a planned course",
            [""] + planned_options,
            key="planner_remove_planned_label",
        )
        if st.button("Remove selected planned course", key="planner_remove_planned_btn"):
            if not remove_label:
                st.error("Choose a planned course to remove.")
            else:
                profile.remove_planned(code_from_label(remove_label), profile_data)
                st.rerun()
    else:
        st.markdown(
            empty_state("No planned courses yet", "Use Add to my plan above."),
            unsafe_allow_html=True,
        )


def render_map() -> None:
    profile_data = st.session_state.profile
    status = profile.course_status(profile_data)
    page_header("Prerequisite Map", "Course prerequisite graph, colored by your personal progress.")

    scope = st.radio(
        "Map scope",
        ["My program", "All UCP IT courses"],
        horizontal=True,
        key="map_scope",
    )
    program = None if scope == "All UCP IT courses" else profile_data["program"]
    courses = catalog.all_courses(program)
    edges = catalog.prerequisite_edges(program)

    dot = [
        "digraph degree_audit {",
        'rankdir="LR";',
        'bgcolor="transparent";',
        'node [shape="box", style="rounded,filled", fontname="Poppins", fontsize="12", fontcolor="white", color="#9cc0ff", penwidth="1.4"];',
        'edge [color="#9cc0ff", arrowhead="vee", penwidth="1.4"];',
    ]
    for course in courses:
        code = course["code"]
        if code in status["passed"]:
            fill = "#20a96b"
        elif code in status["failed"]:
            fill = "#d9534f"
        elif code in {item["code"] for item in profile_data.get("courses", []) if item["grade"] not in catalog.GRADE_POINTS}:
            fill = "#ffd23f"
        else:
            fill = "#53699f"
        title = str(course["title"]).replace('"', "'")
        dot.append(f'"{code}" [label="{code}\\n{title}", fillcolor="{fill}"];')
    for edge in edges:
        dot.append(f'"{edge["from"]}" -> "{edge["to"]}";')
    dot.append("}")

    st.graphviz_chart("\n".join(dot), width="stretch")
    st.caption("Arrows point from a prerequisite to the course it unlocks. Green = passed, red = failed, yellow = in progress/incomplete, blue = not started.")


def render_standing() -> None:
    profile_data = st.session_state.profile
    summary = profile.summary(profile_data)
    standing = summary["standing"]
    program = summary["program"]
    page_header("Standing and Alerts", "Dean's List, probation, and graduation progress for your UCP profile.")

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

    columns = st.columns(3)
    with columns[0]:
        st.markdown(
            metric_card("CGPA", f"{profile_data.get('cgpa', 0):.2f}", "on a 4.0 scale", "◎", compact=True),
            unsafe_allow_html=True,
        )
    with columns[1]:
        st.markdown(
            metric_card("Credits passed", summary["creditsPassed"], f"of {program['credits']} required", "▤", compact=True),
            unsafe_allow_html=True,
        )
    with columns[2]:
        st.markdown(
            metric_card("Credits remaining", summary["creditsRemaining"], "to graduation", "➜", compact=True),
            unsafe_allow_html=True,
        )

    st.progress(summary["progress"] / 100.0)
    st.caption(f"Estimated CGPA from courses entered: {summary['gpaFromCourses']:.2f}.")

    if standing == "Dean's List":
        st.markdown(
            alert(
                "green",
                "Dean's List",
                "Your CGPA is 3.5 or higher. Keep this progress going.",
            ),
            unsafe_allow_html=True,
        )
    elif standing == "Graduation Eligible":
        st.markdown(
            alert(
                "green",
                "Graduation eligible",
                "You meet the credit and CGPA thresholds. Confirm the final audit with your UCP department.",
            ),
            unsafe_allow_html=True,
        )
    elif standing == "Probation":
        st.markdown(
            alert(
                "red",
                "Advisor meeting required",
                "CGPA is below 2.0. Book a meeting with your academic advisor.",
            ),
            unsafe_allow_html=True,
        )
    elif standing == "At Risk":
        st.markdown(
            alert(
                "yellow",
                "Keep an eye on this one",
                "CGPA is between 2.0 and 2.5. Your advisor can help plan the next term.",
            ),
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            alert(
                "green",
                "On track",
                "You are in good standing. Keep the current plan moving.",
            ),
            unsafe_allow_html=True,
        )

    if summary["prerequisiteGaps"]:
        st.markdown('<div class="section-title">Prerequisite gaps</div>', unsafe_allow_html=True)
        for gap in summary["prerequisiteGaps"]:
            st.markdown(
                alert(
                    "yellow",
                    f"{gap['code']} has unmet prerequisite(s)",
                    f"Complete {', '.join(gap['missing'])} before treating {gap['code']} as fully unlocked.",
                ),
                unsafe_allow_html=True,
            )

    st.markdown(
        '<div class="section-title">Standing thresholds</div>', unsafe_allow_html=True
    )
    rows = "".join(
        f"<tr><td>{esc(label)}</td><td>{esc(rule)}</td></tr>"
        for label, rule in [
            ("Probation", "CGPA below 2.0"),
            ("At Risk", "CGPA 2.0 to below 2.5"),
            ("Dean's List", "CGPA 3.5 or higher"),
            ("Graduation Eligible", "CGPA 2.0 or higher and credits passed meet program total"),
            ("Good Standing", "None of the above"),
        ]
    )
    st.markdown(
        '<table class="da-table"><thead><tr><th>Standing</th><th>Rule</th></tr></thead><tbody>'
        + rows
        + "</tbody></table>",
        unsafe_allow_html=True,
    )


def render_agent() -> None:
    page_header("Ask the Agent", "UCP-only academic questions: programs, courses, prerequisites, credits, standing, and your profile.")
    st.markdown(
        '<span class="pill pill-yellow">Scope: UCP IT degrees only</span>',
        unsafe_allow_html=True,
    )

    if not llm_ready():
        st.markdown(
            alert(
                "yellow",
                "Gemini API key needed",
                "Every other page works without a key. To unlock the agent, paste a real key from Google AI Studio into .env and restart the app.",
            ),
            unsafe_allow_html=True,
        )
        st.code("GEMINI_API_KEY=your_real_key_here", language="bash")
        return

    if st.button("Clear chat", key="clear_chat"):
        st.session_state.chat = []
        st.rerun()

    sample_prompts = [
        "What are the prerequisites for AIDC303 Machine Learning?",
        "Which courses can I take next with my current profile?",
        "Am I on the Dean's List?",
        "How many credits do I still need to graduate?",
        "What are the UCP BS Cyber Security domain core courses?",
        "Can I take CP493 Final Year Project II now?",
    ]
    for prompt in sample_prompts:
        if st.button(
            prompt,
            key=f"agent_sample_{prompt.replace(' ', '_').replace('?', '')}",
        ):
            submit_prompt(prompt)

    for message in st.session_state.chat:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
            if message["role"] == "assistant":
                tools = message.get("tools") or []
                st.caption("Tools used: " + (", ".join(tools) if tools else "none"))

    prompt = st.chat_input("Ask about UCP courses, prerequisites, credits, or standing...")
    if prompt:
        submit_prompt(prompt)


def render_explorer() -> None:
    page_header("Ontology Explorer", "Base ontology, live personalized graph, UCP catalog, and competency questions.")
    from audit import queries

    metrics = queries.get_ontology_metrics()
    columns = st.columns(4)
    with columns[0]:
        st.markdown(metric_card("Classes", metrics["classes"], "OWL classes", "▤"), unsafe_allow_html=True)
    with columns[1]:
        st.markdown(metric_card("Object properties", metrics["objectProperties"], "relationships", "◎"), unsafe_allow_html=True)
    with columns[2]:
        st.markdown(metric_card("Data properties", metrics["dataProperties"], "literal values", "▤"), unsafe_allow_html=True)
    with columns[3]:
        st.markdown(metric_card("Individuals", metrics["individuals"], f"{metrics['triples']} base triples", "★"), unsafe_allow_html=True)

    base_tab, live_tab, catalog_tab, cq_tab = st.tabs(["Base ontology", "Live personalized graph", "UCP catalog", "Competency questions"])

    with base_tab:
        classes = queries.get_class_rows()
        frame = pd.DataFrame(
            [{"Class": item["class"], "Parent": item["parent"], "Defined": item["defined"]} for item in classes]
        )
        st.dataframe(frame, hide_index=True, width="stretch")
        properties = queries.get_property_rows()
        frame = pd.DataFrame(
            [{"Property": item["property"], "Kind": item["kind"], "Domain": item["domain"], "Range / type": item["range"]} for item in properties]
        )
        st.dataframe(frame, hide_index=True, width="stretch")

    with live_tab:
        graph_metrics = live_graph.metrics()
        live_columns = st.columns(4)
        with live_columns[0]:
            st.markdown(metric_card("Classes", graph_metrics["classes"], "live classes", "▤"), unsafe_allow_html=True)
        with live_columns[1]:
            st.markdown(metric_card("Object properties", graph_metrics["objectProperties"], "live relationships", "◎"), unsafe_allow_html=True)
        with live_columns[2]:
            st.markdown(metric_card("Data properties", graph_metrics["dataProperties"], "live literals", "▤"), unsafe_allow_html=True)
        with live_columns[3]:
            st.markdown(metric_card("Individuals", graph_metrics["individuals"], f"{graph_metrics['triples']} live triples", "★"), unsafe_allow_html=True)
        st.caption("The live graph overlays the UCP catalog and your saved profile onto the base ontology.")
        triples = live_graph.user_triples()
        if triples:
            frame = pd.DataFrame(triples)
            st.dataframe(frame, hide_index=True, width="stretch")
        else:
            st.markdown(empty_state("No personal triples yet", "Save a profile and add courses in Overview/My Courses to see your live graph."), unsafe_allow_html=True)
        if st.button("Refresh live graph", key="refresh_live_graph"):
            st.rerun()

    with catalog_tab:
        cat_metrics = catalog.catalog_metrics()
        mcol = st.columns(4)
        with mcol[0]:
            st.markdown(metric_card("UCP programs", cat_metrics["programs"], "BSCS, BSDS, BSSE, BSAI, BSCY", "▤"), unsafe_allow_html=True)
        with mcol[1]:
            st.markdown(metric_card("Catalog courses", cat_metrics["courses"], "including custom additions", "◎"), unsafe_allow_html=True)
        with mcol[2]:
            st.markdown(metric_card("Custom courses", cat_metrics["customCourses"], "added by you", "✚"), unsafe_allow_html=True)
        with mcol[3]:
            st.markdown(metric_card("Prerequisite edges", cat_metrics["prerequisiteEdges"], "direct links", "➜"), unsafe_allow_html=True)
        st.markdown('<div class="section-title">Program summaries</div>', unsafe_allow_html=True)
        for program in catalog.list_programs():
            with st.expander(f"{program['code']} - {program['name']} ({program['credits']} credits)"):
                summary = catalog.program_summary(program['code'])
                st.markdown(f"Catalog courses in plan: {summary['catalogCourses']}, catalog credits: {summary['catalogCredits']}.")
                for category, data in summary["categories"].items():
                    st.markdown(f"- {category}: {data['courses']} courses, {data['credits']} credits")
        st.markdown('<div class="section-title">Top prerequisite unlockers</div>', unsafe_allow_html=True)
        unlockers = catalog.top_unlockers(limit=10)
        frame = pd.DataFrame(unlockers)
        st.dataframe(frame, hide_index=True, width="stretch")
        st.markdown('<div class="section-title">Course search</div>', unsafe_allow_html=True)
        search = st.text_input("Search catalog", key="explorer_catalog_search")
        results = catalog.search_courses(search)
        frame = pd.DataFrame(
            [
                {
                    "Code": course["code"],
                    "Title": course["title"],
                    "Credits": course["credits"],
                    "Category": course["category"],
                    "Programs": ", ".join(course["programs"]),
                    "Prerequisites": ", ".join(course["prerequisites"]),
                }
                for course in results[:50]
            ]
        )
        st.dataframe(frame, hide_index=True, width="stretch")
        if len(results) > 50:
            st.caption(f"Showing 50 of {len(results)} matching courses.")

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

if "profile" not in st.session_state:
    st.session_state.profile = profile.load_profile()
if "page" not in st.session_state:
    st.session_state.page = PAGES[0]
if "student_name" not in st.session_state:
    st.session_state.student_name = st.session_state.profile.get("name") or "Student"
if "chat" not in st.session_state:
    st.session_state.chat = []
if "last_add" not in st.session_state:
    st.session_state.last_add = None
if "cq_results" not in st.session_state:
    st.session_state.cq_results = None

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
    summary = profile.summary(st.session_state.profile)
    st.markdown(
        status_card(
            summary["standing"],
            summary["creditsRemaining"],
            st.session_state.profile.get("name") or "Student",
        ),
        unsafe_allow_html=True,
    )

page = st.session_state.page
if page == "Overview":
    render_overview()
elif page == "My Courses":
    render_courses()
elif page == "Course Planner":
    render_planner()
elif page == "Prerequisite Map":
    render_map()
elif page == "Standing and Alerts":
    render_standing()
elif page == "Ask the Agent":
    render_agent()
elif page == "Ontology Explorer":
    render_explorer()
