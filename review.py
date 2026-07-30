# ========================================== 1. Imports ==================================================
import time
from operator import add
from typing import Annotated, Literal

from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langgraph.graph import StateGraph, START, END
from pydantic import BaseModel
from typing_extensions import TypedDict

from number_diff import number_diff, diff_line_map


# =========================================== 2. Setup ==========================================
load_dotenv()
llm = ChatGroq(model="llama-3.3-70b-versatile", temperature=0.5)
CONFIDENCE_THRESHOLD = 0.6


# =========================================== 3. Schemas ===========================================
class ReviewState(TypedDict):
    diff: str
    findings: Annotated[list, add]          

class Findings(BaseModel):
    file: str
    line: int
    severity: Literal["critical", "high", "medium", "low"]
    category: Literal["bug", "security", "performance", "testing",
                      "maintainability", "correctness", "reliability", "documentation"]
    title: str
    description: str
    suggested_fix: str

class Review(BaseModel):
    overall: str
    risk: Literal["low", "medium", "high"]
    findings: list[Findings]

reviewer = llm.with_structured_output(Review)   


# =========================================== 4. Prompts ===========================================
SHARED_RULES = """
Rules:
- Review ONLY the changes in the provided diff. Ignore unchanged code unless a change directly affects it.
- Only report real issues backed by evidence in the diff. Never speculate, assume missing context, or invent problems.
- Prefer reporting nothing over reporting an uncertain or low-value issue.
- Ignore style/formatting/preference nits unless they affect correctness.
- Each diff line is prefixed with its real line number, e.g. "17: +code". Put that exact number in the "line" field. Never guess a line.
- If you find nothing in your area, return an empty findings array.

For each finding: state why it's a problem, its impact, and a concrete fix. Be concise.
"""

SECURITY_PROMPT = f"""
You are a senior application security engineer reviewing a pull request diff.
Focus ONLY on security. Ignore tests, docs, style, and general quality unless they create a security risk.

Look for: injection (SQL, command, XSS, etc.), hardcoded secrets or credentials, authentication/authorization
flaws, unsafe deserialization, path traversal, SSRF, missing/weak input validation, and dangerous functions.
{SHARED_RULES}
"""

QUALITY_PROMPT = f"""
You are a senior software engineer reviewing a pull request diff for correctness.
Focus ONLY on functional correctness. Ignore security, tests, and docs — other reviewers cover those.

Look for: logic errors, off-by-one/boundary mistakes, unhandled edge cases, null/None and type errors,
incorrect error handling, race conditions, resource leaks, and clear runtime bugs.
{SHARED_RULES}
"""

TESTS_PROMPT = f"""
You are a senior engineer reviewing a pull request diff for test coverage.
Focus ONLY on testing. Ignore security, general correctness, and docs — other reviewers cover those.

Look for: new or changed logic with no accompanying tests, important edge cases left untested,
assertions too weak to be meaningful, and brittle or incorrect tests.
{SHARED_RULES}
"""

DOCS_PROMPT = f"""
You are a senior engineer reviewing a pull request diff for documentation clarity.
Focus ONLY on documentation. Ignore security, correctness, and tests — other reviewers cover those.

Look for: new public functions/classes/APIs without docstrings, misleading or outdated comments,
unexplained non-obvious decisions, and unclear names that obscure the change.
{SHARED_RULES}
"""


# =========================================== 5. Specialists ===========================================
def review_specialist(numbered_diff, system_prompt, retries=3):
    for attempt in range(retries):
        try:
            result = reviewer.invoke([("system", system_prompt), ("human", numbered_diff)])
            return result.findings
        except Exception as e:
            if attempt == retries - 1:
                print(f"[specialist] gave up after {retries} attempts: {e}")
                return []                      # degrade: this specialist contributes nothing
            wait = 2 ** attempt                # 1s, 2s, 4s — back off so we don't hammer a limited API
            print(f"[specialist] attempt {attempt + 1} failed: {e} — retrying in {wait}s")
            time.sleep(wait)

def security_node(state):
    return {"findings": review_specialist(state["diff"], SECURITY_PROMPT)}

def quality_node(state):
    return {"findings": review_specialist(state["diff"], QUALITY_PROMPT)}

def test_node(state):
    return {"findings": review_specialist(state["diff"], TESTS_PROMPT)}

def docs_node(state):
    return {"findings": review_specialist(state["diff"], DOCS_PROMPT)}


# =========================================== 6. The LangGraph fan-out ==========================================
builder = StateGraph(ReviewState)

builder.add_node("security_node", security_node)
builder.add_node("quality_node", quality_node)
builder.add_node("test_node", test_node)
builder.add_node("docs_node", docs_node)

builder.add_edge(START, "security_node")
builder.add_edge(START, "quality_node")
builder.add_edge(START, "test_node")
builder.add_edge(START, "docs_node")

builder.add_edge("security_node", END)
builder.add_edge("quality_node", END)
builder.add_edge("test_node", END)
builder.add_edge("docs_node", END)

graph = builder.compile()

def review_all(diff_text, context=""):
    numbered = number_diff(diff_text)
    if context:
        numbered = numbered + "\n\n## Repository facts (context only — do NOT report findings on these lines):\n" + context
    result = graph.invoke({"diff": numbered, "findings": []})
    return result["findings"]            


# =========================================== 7. Confidence pipeline ================================================
def review_samples(diff_text, context="", n=3):
    return [review_all(diff_text, context) for _ in range(n)]

def aggregate_samples(runs):
    n = len(runs)
    counts = {}
    representative = {}
    for run in runs:
        keys_in_this_run = set()
        for f in run:
            key = (f.file, f.line, f.category)
            keys_in_this_run.add(key)
            representative.setdefault(key, f)
        for key in keys_in_this_run:
            counts[key] = counts.get(key, 0) + 1

    merged = []
    for key, count in counts.items():
        f = representative[key]
        merged.append({
            "file": f.file,
            "line": f.line,
            "severity": f.severity,
            "category": f.category,
            "title": f.title,
            "description": f.description,
            "suggested_fix": f.suggested_fix,
            "confidence": count / n,
        })
    return merged

def review_with_confidence(diff_text, context="", n=3):
    runs = review_samples(diff_text, context, n)
    merged = aggregate_samples(runs)
    line_map = diff_line_map(diff_text)
    return [f for f in merged if f["line"] in line_map.get(f["file"], set())]

def is_confident(finding):
    # critical always posts; otherwise it must clear the threshold
    return finding["severity"] == "critical" or finding["confidence"] >= CONFIDENCE_THRESHOLD


# =========================================== 8. Local test ================================================
buggy_diff = """diff --git a/app/users.py b/app/users.py
index 1111111..2222222 100644
--- a/app/users.py
+++ b/app/users.py
@@ -8,3 +8,7 @@ def get_connection():
     return db.connect()
+def get_user(user_id):
+    query = "SELECT * FROM users WHERE id = '" + user_id + "'"
+    return db.execute(query)
"""

if __name__ == "__main__":
    findings = review_with_confidence(buggy_diff, n = 3)
    for f in findings:
        label = "POST " if is_confident(f) else "FLAG "
        print(f"[{label}] {f['confidence']:.0%} {f['severity']} {f['category']} {f['file']}:{f['line']} — {f['title']}")