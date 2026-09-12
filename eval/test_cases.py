"""
Planted-bug test cases for the PR review agent.

Each case is a real unified diff with a KNOWN issue on a KNOWN line (or a
clean diff with no issue at all). The harness runs the agent over each diff
and checks whether the agent flagged the planted line.

`expect` is None for clean diffs (agent should stay silent).
For buggy diffs, `expect` gives the new-file line the finding should land on,
the acceptable categories, and a human label.

Line numbers refer to the NEW file (the "+" side), matching how the agent
numbers diffs. If you edit a diff, re-check the planted line number.
"""

CASES = [
    # ---------------- SECURITY ----------------
    {
        "id": "sql_injection",
        "diff": '''diff --git a/app/users.py b/app/users.py
index 1111111..2222222 100644
--- a/app/users.py
+++ b/app/users.py
@@ -8,3 +8,7 @@ def get_connection():
     return db.connect()
+def get_user(user_id):
+    query = "SELECT * FROM users WHERE id = '" + user_id + "'"
+    return db.execute(query)
''',
        "expect": {"file": "app/users.py", "line": 11,
                   "categories": {"security", "bug"}, "label": "SQL injection via string concat"},
    },
    {
        "id": "command_injection",
        "diff": '''diff --git a/app/ops.py b/app/ops.py
index 1111111..2222222 100644
--- a/app/ops.py
+++ b/app/ops.py
@@ -3,2 +3,5 @@ import os
 import os
+def ping(host):
+    os.system("ping -c 1 " + host)
+    return True
''',
        "expect": {"file": "app/ops.py", "line": 5,
                   "categories": {"security", "bug"}, "label": "command injection via os.system"},
    },
    {
        "id": "hardcoded_secret",
        "diff": '''diff --git a/app/client.py b/app/client.py
index 1111111..2222222 100644
--- a/app/client.py
+++ b/app/client.py
@@ -1,2 +1,4 @@ import requests
 import requests
+API_KEY = "sk_live_4eC39HqLyjWDarjtT1zdp7dc"
+def call():
+    return requests.get("https://api.example.com", headers={"Authorization": API_KEY})
''',
        "expect": {"file": "app/client.py", "line": 3,
                   "categories": {"security"}, "label": "hardcoded API secret"},
    },

    # ---------------- CORRECTNESS ----------------
    {
        "id": "undefined_function",
        "diff": '''diff --git a/app/report.py b/app/report.py
index 1111111..2222222 100644
--- a/app/report.py
+++ b/app/report.py
@@ -5,3 +5,6 @@ def build():
     data = load()
+def summarize(data):
+    cleaned = sanitize_input(data)
+    return cleaned.upper()
''',
        "expect": {"file": "app/report.py", "line": 8,
                   "categories": {"bug", "correctness", "reliability"},
                   "label": "calls sanitize_input, defined nowhere"},
        "needs_context": True,  # only catchable with repo grep context
    },
    {
        "id": "off_by_one",
        "diff": '''diff --git a/app/window.py b/app/window.py
index 1111111..2222222 100644
--- a/app/window.py
+++ b/app/window.py
@@ -2,3 +2,6 @@ def last_n(items, n):
     result = []
+    for i in range(len(items)):
+        if i <= len(items) - n:
+            result.append(items[i])
+    return result
''',
        "expect": {"file": "app/window.py", "line": 5,
                   "categories": {"bug", "correctness"}, "label": "off-by-one in window bound"},
    },
    {
        "id": "none_deref",
        "diff": '''diff --git a/app/cfg.py b/app/cfg.py
index 1111111..2222222 100644
--- a/app/cfg.py
+++ b/app/cfg.py
@@ -4,3 +4,6 @@ def load_config(path):
     cfg = read(path)
+def get_port(path):
+    cfg = read(path)
+    return cfg.get("port").strip()
''',
        "expect": {"file": "app/cfg.py", "line": 7,
                   "categories": {"bug", "correctness", "reliability"},
                   "label": ".strip() on possibly-None .get()"},
    },
    {
        "id": "resource_leak",
        "diff": '''diff --git a/app/io.py b/app/io.py
index 1111111..2222222 100644
--- a/app/io.py
+++ b/app/io.py
@@ -1,2 +1,5 @@ import json
 import json
+def read_json(path):
+    f = open(path)
+    return json.load(f)
''',
        "expect": {"file": "app/io.py", "line": 4,
                   "categories": {"bug", "reliability", "correctness", "maintainability"},
                   "label": "file handle never closed"},
    },

    # ---------------- TESTS ----------------
    {
        "id": "no_tests_for_logic",
        "diff": '''diff --git a/app/discount.py b/app/discount.py
index 1111111..2222222 100644
--- a/app/discount.py
+++ b/app/discount.py
@@ -1,2 +1,7 @@ TAX = 0.1
 TAX = 0.1
+def final_price(base, discount_pct):
+    if discount_pct > 100:
+        raise ValueError("bad discount")
+    price = base * (1 - discount_pct / 100)
+    return price * (1 + TAX)
''',
        "expect": {"file": "app/discount.py", "line": 3,
                   "categories": {"testing"}, "label": "new branching logic, no tests"},
    },

    # ---------------- DOCS ----------------
    {
        "id": "no_docstring_public_api",
        "diff": '''diff --git a/app/api.py b/app/api.py
index 1111111..2222222 100644
--- a/app/api.py
+++ b/app/api.py
@@ -1,2 +1,6 @@ from server import route
 from server import route
+@route("/refund")
+def process_refund(order_id, amount, reason):
+    engine.refund(order_id, amount, reason)
+    return {"ok": True}
''',
        "expect": {"file": "app/api.py", "line": 3,
                   "categories": {"documentation"}, "label": "new public endpoint, no docstring"},
    },

    # ---------------- CLEAN (agent should stay SILENT) ----------------
    {
        "id": "clean_add_docstring",
        "diff": '''diff --git a/app/mathutil.py b/app/mathutil.py
index 1111111..2222222 100644
--- a/app/mathutil.py
+++ b/app/mathutil.py
@@ -1,2 +1,6 @@ import math
 import math
+def circle_area(radius):
+    """Return the area of a circle with the given radius."""
+    if radius < 0:
+        raise ValueError("radius must be non-negative")
+    return math.pi * radius * radius
''',
        "expect": None,  # correct, documented, validated — nothing to flag
    },
    {
        "id": "clean_rename_comment",
        "diff": '''diff --git a/README.md b/README.md
index 1111111..2222222 100644
--- a/README.md
+++ b/README.md
@@ -1,3 +1,4 @@
 # Project
 Setup instructions below.
+Run `make test` before opening a PR.
''',
        "expect": None,  # doc-only, harmless
    },
]
