# Degree Audit Assistant - Reference Demo Transcript

This is a reference transcript. The tool results shown below are the verified
outputs of `audit/queries.py`; at runtime Gemini chooses the tools and writes
the final natural-language phrasing from those results.

---

## Demo 1 - Blocked course

**User:** Can Ayesha take Machine Learning next?

**Tool calls (reference):**

```text
get_next_eligible_courses("Student_Ayesha")
  -> ["AI401", "DB301", "ETH101", "LA201"]

get_prerequisite_chain("ML402")
  -> ["AI401", "DS301", "LA201", "MATH101", "OOP201", "PF101"]

get_completed_courses("Student_Ayesha")
  -> ["DS301", "MATH101", "OOP201", "PF101"]
```

**Assistant (expected answer):**

No. Ayesha still needs AI401 and LA201 before she can take ML402 Machine
Learning.

**Tool caption shown in the app:**

```text
Tools used: get_next_eligible_courses, get_prerequisite_chain, get_completed_courses
```

---

## Demo 2 - Next courses

**User:** Which courses can Ayesha take next?

**Tool call:**

```text
get_next_eligible_courses("Student_Ayesha")
  -> ["AI401", "DB301", "ETH101", "LA201"]
```

**Assistant (expected answer):**

Ayesha can take AI401 (Introduction to AI), DB301 (Databases), ETH101 (Ethics in
Computing) and LA201 (Linear Algebra) next.

---

## Demo 3 - Probation and advisor

**User:** Who is on probation, and who is their advisor?

**Tool calls (reference):**

```text
get_student_summary("Student_Ayesha")   -> Dean's List, advisor Khan
get_student_summary("Student_Bilal")    -> Probation, advisor Khan
get_student_summary("Student_Hina")     -> At Risk, advisor Siddiqui
get_student_summary("Student_Zain")     -> Graduation Eligible, advisor Siddiqui
get_student_summary("Student_Maryam")   -> Dean's List, advisor Siddiqui
```

**Assistant (expected answer):**

Bilal is on probation with a CGPA of 1.8. His advisor is Khan.

---

## Demo 4 - Credits remaining

**User:** How many credits does Hina still need?

**Tool call:**

```text
get_credits_remaining("Student_Hina")
  -> 10
```

**Assistant (expected answer):**

Hina still needs 10 credits to graduate.

---

## Demo 5 - Retake

**User:** What must Bilal retake?

**Tool call:**

```text
get_courses_to_retake("Student_Bilal")
  -> ["PF101"]
```

**Assistant (expected answer):**

Bilal must retake PF101 Programming Fundamentals, which he failed in Fall 2024.

---

## Demo 6 - Prerequisite chain

**User:** What are the prerequisites of Machine Learning?

**Tool call:**

```text
get_prerequisite_chain("ML402")
  -> ["AI401", "DS301", "LA201", "MATH101", "OOP201", "PF101"]
```

**Assistant (expected answer):**

Machine Learning (ML402) requires AI401, LA201, DS301, OOP201, PF101 and
MATH101, directly or indirectly.

---

## Guardrail checks

| Situation | Expected behaviour |
|-----------|--------------------|
| Tool returns an empty list | The agent says the ontology has no data for that question. |
| Gemini key missing or placeholder | The Ask the Agent page shows setup instructions; other pages still work. |
| Invalid student or course input | The data layer raises a validation error; no SPARQL is written by the LLM. |
| Unknown course title | The lookup resolves known titles/codes from the ontology; otherwise it reports that the course is unknown. |
