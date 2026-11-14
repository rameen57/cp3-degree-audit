# Degreely - University Degree Audit and Compliance

A Protégé-compatible OWL ontology plus a Python data layer, MCP server, Gemini
agent and a game-style Streamlit app. The app checks degree progress: passed
courses, prerequisites, credits remaining, retakes and academic standing.

The project follows the CP3 specification for the University Degree Audit and
Compliance Ontology (course ABM, CP3).

---

## Quick start (Windows)

Double-click **`run_app.bat`** in this folder. On first run it creates `.venv`,
installs the requirements and starts the app at <http://localhost:8501>.

To use the AI agent, open `.env` and paste a Gemini API key from Google AI
Studio:

```text
GEMINI_API_KEY=your_real_key_here
GEMINI_MODEL=gemini-3.5-flash
ONTOLOGY_PATH=ontology/degree_audit.ttl
```

Without a key every page except **Ask the Agent** still works.

### Manual start

```bat
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
streamlit run app/app.py
```

WSL / macOS:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
streamlit run app/app.py
```

### Run from VS Code

1. Open this folder in VS Code.
2. Install the Python extension if VS Code asks.
3. Select `.venv\Scripts\python.exe` as the interpreter.
4. Press **F5** and choose **Degreely app (Streamlit)**.

`.vscode/launch.json` also contains configurations for the MCP server and the
competency-question runner.

---

## Project layout

```text
cp3-degree-audit/
├── data/
│   ├── ucp_catalog.json        Indicative UCP IT course catalog (125 courses, 5 programs)
│   ├── custom_courses.json     User-added courses (ignored by git)
│   └── my_profile.json         Saved personal profile (ignored by git)
├── ontology/
│   ├── degree_audit.ttl        OWL ontology (Turtle, with SWRL rules)
│   ├── degree_audit.owl        Same ontology as RDF/XML for Protégé
│   └── queries.rq              CQ1-CQ8 with expected results
├── audit/
│   ├── config.py               .env loading and llm_ready()
│   ├── queries.py              SPARQL data layer (base ontology tools + page helpers)
│   ├── catalog.py              UCP catalog, prerequisites, grade verification, web search
│   ├── profile.py              Persistent personal profile, courses, standing, planner helpers
│   └── live_graph.py           In-memory personalized RDF graph for the explorer
├── agent/
│   ├── agent.py                Gemini UCP-scoped agent with catalog/profile/web tools
│   └── mcp_server.py           FastMCP server exposing the seven base ontology tools
├── app/
│   ├── app.py                  Streamlit app (personalized seven missions)
│   └── style.css               Blue game-style theme
├── scripts/
│   └── run_queries.py          Runs CQ1-CQ8 and prints results
├── docs/
│   ├── REPORT.md               Design and verification report
│   ├── DEMO_TRANSCRIPT.md      Reference demo transcript
│   └── screenshots/            Captured app screenshots
├── .vscode/                    Interpreter, launch and task configuration
├── .env.example                Safe placeholder configuration
├── .streamlit/config.toml      Dark theme base
├── requirements.txt
├── run_app.bat                 One-click setup + launch
├── run_queries.bat             One-click CQ runner
├── run_app.sh                  WSL/macOS launcher
└── README.md
```

---

## The seven missions

| # | Page | What it shows | Data source |
|---|------|---------------|-------------|
| 1 | Overview | Editable personal profile: name, roll number, UCP program, semester, CGPA; credits passed/remaining and standing | `audit/profile.py`, `audit/catalog.py` |
| 2 | My Courses | Add verified UCP courses with grades and terms; passed/failed/in-progress lists; prerequisite gaps; remove or clear courses | `profile.add_course`, `catalog.verify_grade`, `catalog.prerequisite_chain` |
| 3 | Course Planner | Searchable UCP catalog (type or choose), course metadata, prerequisite chain, missing prerequisites, unlocks, add/remove from plan | `catalog.search_courses`, `profile.plan_course` |
| 4 | Prerequisite Map | Course prerequisite graph for your program or all UCP IT courses, colored by your personal progress | `catalog.prerequisite_edges`, profile status |
| 5 | Standing and Alerts | Dean's List, probation/at-risk, graduation-eligible, progress bar, thresholds and prerequisite gaps | `profile.summary`, `profile.get_my_standing` |
| 6 | Ask the Agent | UCP-only chat: programs, courses, prerequisites, credits, standing, profile, and Google Search for official UCP sources | `agent/agent.py`, `audit/catalog.py` |
| 7 | Ontology Explorer | Base ontology metrics/properties/CQs, live personalized RDF graph, UCP catalog summaries and search | `audit/queries.py`, `audit/live_graph.py`, `audit/catalog.py` |

Your personal profile is stored in `data/my_profile.json`; user-added catalog courses are stored in `data/custom_courses.json`. Both are ignored by git. The base ontology, CP3 competency questions, seven MCP tools, and CQ1-CQ8 results remain unchanged for the original ontology deliverable.

## Personalization and UCP catalog

- **Overview**: enter or edit your name, roll number, program, semester, and CGPA. Save once; every page uses your profile.
- **My Courses**: choose a UCP catalog course or add a custom course, select a grade and term, then verify and add. Grades D or better count as passed; F must be retaken.
- **Course Planner**: search or type UCP course codes across all five IT programs. See credits, category, direct and full prerequisite chains, missing prerequisites, and courses the selected course unlocks. Add courses to your plan.
- **Standing and Alerts**: standing is computed from your profile CGPA and credits passed. Dean's List requires CGPA >= 3.5; graduation eligible requires CGPA >= 2.0 and credits passed meeting the program total.
- **Ask the Agent**: answers UCP questions only and can use Google Search for official UCP sources.
- **Ontology Explorer**: shows the base ontology plus a live personalized RDF graph with your profile and courses.

The catalog in `data/ucp_catalog.json` is indicative and compiled from published UCP roadmaps; confirm final requirements with your department.

---

## Ontology summary

Namespace: `http://example.org/ontologies/degree-audit#` (prefix `da:`)

Measured from the TTL with rdflib:

| Metric | Count |
|--------|-------|
| Classes | 15 (11 asserted, 4 defined) |
| Object properties | 19 |
| Data properties | 13 |
| Individuals | 35 |
| SWRL rules | 4 |
| Competency questions | 8 |
| Graph triples | 717 |

### Defined classes

```text
ProbationStudent          : Student and (cgpa some xsd:decimal[< 2.0])
AtRiskStudent             : Student and (cgpa some xsd:decimal[>= 2.0, < 2.5])
DeansListStudent          : Student and (cgpa some xsd:decimal[>= 3.5])
GraduationEligibleStudent : Student and (cgpa some xsd:decimal[>= 2.0])
                                    and (totalCreditsEarned some xsd:integer[>= 130])
```

### SWRL rules

```text
R1: Student(?s) ^ hasEnrollment(?s, ?e) ^ passed(?e, true)  ^ forCourse(?e, ?c) -> hasCompleted(?s, ?c)
R2: Student(?s) ^ hasEnrollment(?s, ?e) ^ passed(?e, false) ^ forCourse(?e, ?c) -> mustRetake(?s, ?c)
R3: ProbationStudent(?s) ^ hasAdvisor(?s, ?a) -> needsAdvisorMeeting(?s, ?a)
R4: Student(?s) ^ hasAdvisor(?s, ?a) ^ worksIn(?a, ?d) -> affiliatedWith(?s, ?d)
```

The SWRL rules are embedded in `degree_audit.ttl` / `.owl` and can be reviewed in
Protégé's SWRLTab. The app's SPARQL queries use asserted data, so a reasoner is
not required at runtime.

---

## Verified competency question results

Run `python scripts/run_queries.py` or open **Ontology Explorer > Run CQ1 - CQ8**
in the app.

| CQ | Question | Expected | Verified |
|----|----------|----------|----------|
| CQ1 | Direct and indirect prerequisites of ML402 | AI401, LA201, DS301, OOP201, PF101, MATH101 | Same set |
| CQ2 | Courses Ayesha passed | PF101, OOP201, DS301, MATH101 | Same set |
| CQ3 | Courses Ayesha can take next | DB301, AI401, LA201, ETH101 | Same set |
| CQ4 | Students below 2.0 CGPA | Student_Bilal (1.8) | Student_Bilal |
| CQ5 | Credits remaining | Ayesha 34, Bilal 70, Hina 10, Zain 0, Maryam 100 | Same |
| CQ6 | Failed courses | Bilal: PF101; Hina: DS301 | Same |
| CQ7 | Probation students per advisor | Advisor_Khan: 1 | Same |
| CQ8 | Courses that unlock the most later courses | PF101 (6), then OOP201 (5) | Same |

---

## Agent tools

The MCP server still exposes the seven base ontology tools from `audit/queries.py`.
The Gemini agent adds UCP personalization tools and operates strictly inside
University of Central Punjab academic scope:

| Tool | Input | Returns |
|------|-------|---------|
| `get_my_profile` | none | Name, roll number, program, semester, CGPA |
| `get_my_courses` | none | Recorded courses with grades, terms and pass status |
| `get_my_standing` | none | Standing, CGPA, credits passed/required |
| `get_my_remaining_credits` | none | Credits remaining to graduate |
| `get_my_eligible_courses` | none | UCP courses whose prerequisites are passed |
| `plan_ucp_course` | course code | Locked/ready/retake state, missing prerequisites, unlocks |
| `search_ucp_courses` | query, program | Matching UCP catalog courses |
| `get_ucp_course_details` | course code | Course title, credits, category, prerequisites |
| `verify_ucp_grade` | course code, grade | Pass/fail and credit eligibility for the grade |
| `search_ucp_web` | query | Official UCP information via Google Search grounding |

Supported UCP IT degrees: BS Computer Science, BS Data Science, BS Software
Engineering, BS Artificial Intelligence, and BS Cyber Security.

Guardrails:

- The agent answers only UCP academic questions and politely refuses non-UCP topics.
- It uses catalog/profile tools first; web search is used only for official UCP sources.
- It never invents course codes, prerequisites, credit hours, grades, or rules.
- Without a valid API key the app shows a friendly setup message; Google Search may also be limited by API quota.
- The key lives in `.env`, which is ignored by git.

Start the MCP server (optional):

```bat
.venv\Scripts\python.exe agent\mcp_server.py
```

---

## Demo questions

| Question | Expected answer |
|----------|-----------------|
| Can Ayesha take Machine Learning next? | No. She still needs AI401 and LA201. |
| Which courses can Ayesha take next? | DB301, AI401, LA201, ETH101 |
| Who is on probation, and who is their advisor? | Bilal (CGPA 1.8), advisor Khan |
| How many credits does Hina still need? | 10 |
| What must Bilal retake? | PF101 |
| What are the prerequisites of Machine Learning? | AI401, LA201, DS301, OOP201, PF101, MATH101 |

See `docs/DEMO_TRANSCRIPT.md` for the reference tool-call flow.

---

## Protégé verification

Protégé works independently of VS Code and Python. Open the `.owl` file, not the
`.ttl`, for the cleanest load.

1. Open `ontology/degree_audit.owl` in Protégé Desktop (`File > Open`, then
   choose **Open as ontology** if prompted). The `.owl` file is RDF/XML and was
   validated with the OWL API bundled in Protégé 5.6.9: loaded successfully, 501
   axioms, 15 classes, 19 object properties, 13 data properties, 35 individuals,
   4 SWRL rules, and it conforms to the OWL 2 DL profile. HermiT reports the
   ontology consistent and derives the expected defined-class instances. The
   `.ttl` file is the app's source format; Protégé can read it, but `.owl` is the
   intended Protégé deliverable.
2. Run **Reasoner > HermiT > Start reasoner**.
3. Run these DL Query expressions in the **DL Query** tab:

| DL Query | Expected instances |
|----------|--------------------|
| `ProbationStudent` | Student_Bilal |
| `AtRiskStudent` | Student_Hina |
| `DeansListStudent` | Student_Ayesha, Student_Maryam |
| `GraduationEligibleStudent` | Student_Zain |
| `requiresCourse value PF101` | OOP201, DS301, DB301, AI401, ML402, NLP410 |

4. Open **Window > Tabs > SWRLTab** to review rules R1-R4. Use the SWRLTab's
   rule engine to see `hasCompleted`, `mustRetake`, `needsAdvisorMeeting` and
   `affiliatedWith` assertions.
5. Consistency test: temporarily assert `Student_Bilal` as an `Advisor`; HermiT
   should report the ontology inconsistent because Student and Advisor are
   disjoint. Remove the assertion afterwards.
6. Run CQ1-CQ8 in the **SPARQL Query** tab and compare with the table above.

Note: HermiT handles OWL DL class/property inferences; SWRL execution is done by
the SWRLTab's rule engine (Drools). The Python app deliberately runs its fixed
SPARQL queries on asserted data so it works without a reasoner.

---

## Troubleshooting

- **Gemini key message on Ask the Agent**: fill `GEMINI_API_KEY` in `.env` and
  restart Streamlit. Placeholder values are rejected.
- **MCP import error mentioning `MCPServer`**: install the pinned `mcp<2`
  requirement. `mcp` 2.x renamed `FastMCP` to `MCPServer`.
- **Port 8501 in use**: run
  `streamlit run app/app.py --server.port 8502`.
- **First run is slow**: `run_app.bat` installs packages into `.venv`; later
  starts are immediate.
- **Venv moved from another machine**: delete `.venv` and run `run_app.bat`
  again so it is rebuilt.

---

## Source data note

Course codes, titles, grades, CGPA and credit values are illustrative sample
data created for the CP3 project. The ontology is the single source of truth for
the app.
