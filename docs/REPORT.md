# University Degree Audit and Compliance - Project Report

## 1. Scenario

A degree audit answers whether a student is on track to graduate: which courses
are passed, which prerequisites block the next course, how many credits remain
and what academic standing the student holds. This project encodes those rules
in OWL, answers audit questions with SPARQL, exposes the queries as MCP tools and
lets a Gemini-powered agent explain the results in plain language.

The front end, **Degreely**, is a Streamlit app styled as a blue game interface
with seven missions. Every displayed number comes from the ontology through
`audit/queries.py`; the UI contains no hard-coded student facts.

## 2. Architecture

```text
Ontology      ontology/degree_audit.ttl + .owl
              OWL 2 classes, properties, individuals, SWRL rules
                  |
Data layer    audit/queries.py
              Seven tool functions + page helpers, fixed SPARQL over rdflib
                  |
      +-----------+-------------+
      |                         |
Agent                     Front end
agent/agent.py            app/app.py + app/style.css
Gemini function calling   Seven Streamlit pages
      |
MCP interface
agent/mcp_server.py
FastMCP exposing the same seven tools
```

Configuration lives in `audit/config.py` and `.env`. The Gemini key is never
hard-coded and `.env` is git-ignored.

## 3. Ontology design

Namespace: `http://example.org/ontologies/degree-audit#` (prefix `da:`)

### 3.1 Classes (15)

| Class | Parent | Meaning |
|-------|--------|---------|
| Person | owl:Thing | Any person |
| Student | Person | A student in a program |
| Advisor | Person | Academic advisor |
| Department | owl:Thing | Academic department |
| Program | owl:Thing | Degree program |
| Course | owl:Thing | Catalog course |
| CoreCourse | Course | Mandatory course |
| ElectiveCourse | Course | Optional course |
| Semester | owl:Thing | Teaching term |
| Enrollment | owl:Thing | Student-course-term record |
| Requirement | owl:Thing | Program requirement block |
| ProbationStudent | Student | Defined, inferred |
| DeansListStudent | Student | Defined, inferred |
| AtRiskStudent | Student | Defined, inferred |
| GraduationEligibleStudent | Student | Defined, inferred |

Pairwise disjointness covers Person, Department, Program, Course, Semester,
Enrollment and Requirement. Student and Advisor are disjoint; CoreCourse and
ElectiveCourse are disjoint.

### 3.2 Defined classes

```text
ProbationStudent          : Student and (cgpa some xsd:decimal[< 2.0])
AtRiskStudent             : Student and (cgpa some xsd:decimal[>= 2.0, < 2.5])
DeansListStudent          : Student and (cgpa some xsd:decimal[>= 3.5])
GraduationEligibleStudent : Student and (cgpa some xsd:decimal[>= 2.0])
                                    and (totalCreditsEarned some xsd:integer[>= 130])
```

### 3.3 Properties

Nineteen object properties include `hasAdvisor` (functional, inverse of
`advises`), `enrolledInProgram` (functional), `requiresCourse` (transitive),
`hasPrerequisite` (asymmetric, sub-property of `requiresCourse`),
`hasEnrollment` / `enrollmentOf` (inverses), and the four rule-produced
properties `hasCompleted`, `mustRetake`, `needsAdvisorMeeting` and
`affiliatedWith`.

Thirteen data properties cover names, student IDs, CGPA, earned credits, course
code/title/credits, grades, pass flag, program thresholds, requirement credits
and semester names.

### 3.4 SWRL rules

```text
R1: Student(?s) ^ hasEnrollment(?s, ?e) ^ passed(?e, true)  ^ forCourse(?e, ?c) -> hasCompleted(?s, ?c)
R2: Student(?s) ^ hasEnrollment(?s, ?e) ^ passed(?e, false) ^ forCourse(?e, ?c) -> mustRetake(?s, ?c)
R3: ProbationStudent(?s) ^ hasAdvisor(?s, ?a) -> needsAdvisorMeeting(?s, ?a)
R4: Student(?s) ^ hasAdvisor(?s, ?a) ^ worksIn(?a, ?d) -> affiliatedWith(?s, ?d)
```

The rules are embedded in both `degree_audit.ttl` and `degree_audit.owl`. They
can be inspected and executed in Protégé's SWRLTab.

### 3.5 Sample data

- Program_BSAI: 130 credits, minimum CGPA 2.0, managed by Dept_ComputerScience.
- 10 courses: 8 core, 2 elective, with the prerequisite chain
  PF101 → OOP201 → DS301 → AI401 → ML402 → NLP410 plus MATH101 → LA201 → ML402.
- 5 students: Ayesha (3.7 / 96), Bilal (1.8 / 60), Hina (2.3 / 120),
  Zain (3.0 / 132), Maryam (3.9 / 30).
- 11 enrollments across Fall 2024, Spring 2025 and Fall 2025.
- 2 requirements: Req_Core (24 credits) and Req_Elective (3 credits).

Full details are in `ontology/degree_audit.ttl` and section 4 of the CP3 brief.

## 4. Measured ontology metrics

Measured with rdflib on `ontology/degree_audit.ttl`:

| Metric | Measured |
|--------|----------|
| Classes | 15 |
| Object properties | 19 |
| Data properties | 13 |
| Individuals | 35 |
| SWRL rules | 4 |
| Graph triples | 717 |

The Active ontology tab in Protégé should show the same design counts. SWRL
variables are represented with `swrl:Variable` and are not counted as named
individuals by this measurement.

## 5. Verification

### 5.1 DL Query expectations (Protégé + HermiT)

The `.owl` file was loaded with the OWL API bundled in Protégé 5.6.9 (501
axioms, 15 classes, 19 object properties, 13 data properties, 35 individuals, 4
SWRL rules, OWL 2 DL profile OK). HermiT reported the ontology consistent and
returned exactly the instances below.

| DL Query | Expected instances |
|----------|--------------------|
| `ProbationStudent` | Student_Bilal |
| `AtRiskStudent` | Student_Hina |
| `DeansListStudent` | Student_Ayesha, Student_Maryam |
| `GraduationEligibleStudent` | Student_Zain |
| `requiresCourse value PF101` | OOP201, DS301, DB301, AI401, ML402, NLP410 |

### 5.2 Rule results expected in Protégé

| Student | Inferred properties |
|---------|---------------------|
| Student_Ayesha | hasCompleted PF101, OOP201, DS301, MATH101 |
| Student_Bilal | hasCompleted MATH101; mustRetake PF101; needsAdvisorMeeting Advisor_Khan |
| Student_Hina | hasCompleted PF101, OOP201; mustRetake DS301 |
| Student_Maryam | hasCompleted PF101, MATH101 |

Every student is also `affiliatedWith Dept_ComputerScience` through R4.

### 5.3 Competency question results (verified with rdflib)

| CQ | Expected | Actual |
|----|----------|--------|
| CQ1 | AI401, LA201, DS301, OOP201, PF101, MATH101 | All six returned |
| CQ2 | PF101, OOP201, DS301, MATH101 | All four returned |
| CQ3 | DB301, AI401, LA201, ETH101 | All four returned |
| CQ4 | Student_Bilal (1.8) | Student_Bilal (1.8) |
| CQ5 | Ayesha 34, Bilal 70, Hina 10, Zain 0, Maryam 100 | Same values |
| CQ6 | Bilal: PF101; Hina: DS301 | Same rows |
| CQ7 | Advisor_Khan: 1 | Advisor_Khan: 1 |
| CQ8 | PF101 (6), then OOP201 (5) | PF101 6, OOP201 5 |

### 5.4 Tool results

The seven tools in `audit/queries.py` were exercised for every student:

```text
get_student_summary("Ayesha")          -> CGPA 3.7, 96 credits, Dean's List, Advisor Khan
get_completed_courses("Ayesha")        -> DS301, MATH101, OOP201, PF101
get_next_eligible_courses("Ayesha")    -> AI401, DB301, ETH101, LA201
get_prerequisite_chain("ML402")        -> AI401, DS301, LA201, MATH101, OOP201, PF101
get_credits_remaining("Hina")          -> 10
get_standing("Zain")                   -> Graduation Eligible
get_courses_to_retake("Bilal")         -> PF101
```

## 6. Front end

Seven missions are implemented and were smoke-tested for all five students:

1. **Overview** - hero, player profile form, Load student action, four metrics.
2. **My Courses** - passed table with grades/semesters and retake alerts.
3. **Course Planner** - unlocked course cards and a picker that names blocking
   prerequisites. Selecting ML402 for Ayesha reports AI401 and LA201.
4. **Prerequisite Map** - Graphviz map with passed green, failed red and
   not-started grey nodes.
5. **Standing and Alerts** - standing badge, advisor card, probation alert and
   CQ7 watchlist.
6. **Ask the Agent** - Gemini chat with tool-usage captions; friendly key setup
   state when the API key is missing.
7. **Ontology Explorer** - measured class/property counts, class and property
   tables, and live CQ1-CQ8 execution.

The acceptance checks were verified in a real browser:

- Ayesha's next courses are AI401, DB301, ETH101 and LA201.
- Hina has 10 credits remaining.
- Bilal is on probation with 70 credits remaining and must retake PF101.
- Switching students updates the sidebar and every page.
- The app starts with one command on Windows.

Screenshots are in `docs/screenshots/`.

## 7. Notes and limitations

- rdflib executes SPARQL only; it does not run OWL/SWRL reasoning. The app uses
  asserted enrollment data for completed and failed courses, which matches the
  rule outputs for the sample data.
- In Protégé, HermiT derives OWL class membership and transitive property
  assertions. SWRL execution is provided by the SWRLTab rule engine.
- The Gemini agent requires a free API key. Without a key, the other six pages
  remain fully functional.
- The illustrative course data is not a real university catalog.
