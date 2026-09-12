"""
Run the PR review agent over the planted-bug test set and report metrics.

Usage (from the repo root, with your .env holding GROQ_API_KEY):
    python eval/run_eval.py
    python eval/run_eval.py --samples 3     # self-consistency runs per diff (default 3)
    python eval/run_eval.py --tolerance 1   # allowed line-number slack (default 1)

What it measures
----------------
- Detection rate: of the planted bugs, how many the agent flagged on the
  right line (within tolerance) in an acceptable category.
- False positives on CLEAN diffs: findings posted on code that has no planted
  bug. This is the honest test of whether the agent knows when to stay quiet.
- Per-category breakdown so you can say which reviewers are strong/weak.

The numbers this prints are the ones you can put on your resume and defend,
because they come from your real agent code, not from a description of it.
"""

import sys, os, argparse
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from review import review_with_confidence, is_confident   # your real agent
from search import repo_context
from eval.test_cases import CASES


def line_matches(found_line, expected_line, tol):
    return abs(int(found_line) - int(expected_line)) <= tol


def score_case(case, samples, tolerance):
    """Return (status, detail). status in {'hit','miss','fp_on_clean','clean_ok'}."""
    diff = case["diff"]
    # Buggy cases that need repo context (e.g. undefined-symbol) can't use grep
    # here because we have no real clone; note it so the result is honest.
    findings = review_with_confidence(diff, context="", n=samples)
    posted = [f for f in findings if is_confident(f)]

    if case["expect"] is None:
        # CLEAN diff: any posted finding is a false positive
        if not posted:
            return "clean_ok", "stayed silent (correct)"
        return "fp_on_clean", f"{len(posted)} finding(s) on clean code: " + \
            ", ".join(f"{f['file']}:{f['line']}/{f['category']}" for f in posted)

    exp = case["expect"]
    for f in posted:
        if (f["file"] == exp["file"]
                and line_matches(f["line"], exp["line"], tolerance)
                and f["category"] in exp["categories"]):
            return "hit", f"caught on {f['file']}:{f['line']} ({f['category']}, conf {f['confidence']:.0%})"

    # not caught on the right line/category — was anything posted at all?
    if posted:
        near = ", ".join(f"{f['file']}:{f['line']}/{f['category']}" for f in posted)
        return "miss", f"planted line missed; agent posted elsewhere: {near}"
    return "miss", "agent posted nothing"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--samples", type=int, default=3)
    ap.add_argument("--tolerance", type=int, default=1)
    args = ap.parse_args()

    buggy = [c for c in CASES if c["expect"] is not None]
    clean = [c for c in CASES if c["expect"] is None]

    hits = 0
    fp_cases = 0
    by_cat = defaultdict(lambda: [0, 0])  # category -> [hit, total]

    print(f"\nRunning {len(CASES)} cases "
          f"({len(buggy)} planted bugs, {len(clean)} clean), "
          f"{args.samples} samples each...\n")

    for case in CASES:
        status, detail = score_case(case, args.samples, args.tolerance)
        if case["expect"] is not None:
            cat = sorted(case["expect"]["categories"])[0]
            by_cat[cat][1] += 1
            if status == "hit":
                hits += 1
                by_cat[cat][0] += 1
            mark = "PASS" if status == "hit" else "MISS"
            note = "" if not case.get("needs_context") else "  [needs repo context]"
            print(f"  [{mark}] {case['id']:<24} {detail}{note}")
        else:
            if status == "fp_on_clean":
                fp_cases += 1
                print(f"  [FP  ] {case['id']:<24} {detail}")
            else:
                print(f"  [OK  ] {case['id']:<24} {detail}")

    print("\n" + "=" * 60)
    print(f"Detection rate : {hits}/{len(buggy)} planted bugs caught "
          f"({hits/len(buggy)*100:.0f}%)")
    print(f"Clean diffs    : {len(clean)-fp_cases}/{len(clean)} kept silent "
          f"({fp_cases} false-positive case(s))")
    print("Per category   :")
    for cat, (h, t) in sorted(by_cat.items()):
        print(f"    {cat:<15} {h}/{t}")
    print("=" * 60)
    print("\nNote: cases marked [needs repo context] are harder here because this")
    print("harness passes no grep context. Your live agent DOES pass context, so")
    print("real-world detection on those is expected to be equal or better.\n")


if __name__ == "__main__":
    main()
