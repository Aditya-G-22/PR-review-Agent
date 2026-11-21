import os
import requests
import hmac, hashlib, json
import shutil
from clone import clone_pr
from search import repo_context
from dotenv import load_dotenv
from collections import defaultdict
from fastapi import FastAPI, Header, Request, HTTPException, BackgroundTasks
from fastapi.responses import RedirectResponse
from review import review_with_confidence, is_confident
from db import init_db, save_review, SessionLocal, Review, already_reviewed

load_dotenv()

app = FastAPI()
init_db()   # create tables on startup if they don't exist yet

def post_inline_comment(repo, number, commit_id, path, line, text):
    url = f"https://api.github.com/repos/{repo}/pulls/{number}/comments"
    headers = {
        "Authorization": f"Bearer {os.getenv('GITHUB_TOKEN')}",
        "Accept": "application/vnd.github+json",
    }
    body = {
        "body": text,
        "commit_id": commit_id,
        "path": path,
        "line": line,
        "side": "RIGHT",
    }
    return requests.post(url, headers=headers, json=body)

def run_review(repo, number):
    print(f"[background] START review for {repo} PR #{number}")
    try:
        diff_url = f"https://github.com/{repo}/pull/{number}.diff"
        diff_text = requests.get(diff_url).text

        headers = {
            "Authorization": f"Bearer {os.getenv('GITHUB_TOKEN')}",
            "Accept": "application/vnd.github+json",
        }
        pr = requests.get(f"https://api.github.com/repos/{repo}/pulls/{number}", headers=headers).json()
        commit_id = pr["head"]["sha"]

        # Idempotency: GitHub can re-deliver a webhook, and a reopened PR fires again.
        # If this exact commit was already reviewed, skip — no duplicate comments, no wasted LLM calls.
        if already_reviewed(repo, number, commit_id):
            print(f"[background] SKIP {repo} PR #{number} @ {commit_id[:7]} — already reviewed")
            return

        folder = clone_pr(repo, commit_id)
        try:
            context = repo_context(diff_text, folder)
            findings = review_with_confidence(diff_text, context)

            by_line = defaultdict(list)
            for f in findings:
                by_line[(f["file"], f["line"])].append(f)

            for (file, line), group in by_line.items():
                blocks = []
                for f in group:
                    prefix = "" if is_confident(f) else "⚠️ LOW CONFIDENCE — please verify · "
                    blocks.append(
                        f"**{prefix}{f['severity'].upper()} · {f['category']} — {f['title']}**\n\n"
                        f"{f['description']}\n\n"
                        f"**Fix:** {f['suggested_fix']}\n\n"
                        f"_confidence: {f['confidence']:.0%}_" 
                    )
                post_inline_comment(repo, number, commit_id, file, line, "\n\n---\n\n".join(blocks))

            # Persist this review + its findings (posted vs flagged-only recorded per finding)
            for f in findings:
                f["posted"] = is_confident(f)
            save_review(repo, number, commit_id, findings)
        finally:
            shutil.rmtree(folder, ignore_errors=True)

        print(f"[background] DONE review for {repo} PR #{number}")
    except Exception as e:
        print(f"[background] review FAILED for {repo} PR #{number}: {e}")


@app.get("/")
def root():
    # Bare URL → the interactive API docs, so the live service shows something useful.
    return RedirectResponse(url="/docs")

@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/reviews")
def list_reviews(limit: int = 20):
    """Most recent reviews (newest first), each with its findings."""
    db = SessionLocal()
    try:
        reviews = (db.query(Review)
                     .order_by(Review.created_at.desc())
                     .limit(limit)
                     .all())
        return [
            {
                "id": r.id,
                "repo": r.repo,
                "pr_number": r.pr_number,
                "commit_sha": r.commit_sha,
                "status": r.status,
                "created_at": r.created_at.isoformat() if r.created_at else None,
                "findings": [
                    {
                        "file": f.file,
                        "line": f.line,
                        "category": f.category,
                        "severity": f.severity,
                        "title": f.title,
                        "confidence": f.confidence,
                        "posted": f.posted,
                    }
                    for f in r.findings
                ],
            }
            for r in reviews
        ]
    finally:
        db.close()

@app.post("/webhook")
async def receive_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    x_github_event: str = Header(None),
    x_hub_signature_256: str = Header(None),
):
    raw_body = await request.body()
    secret = os.getenv("GITHUB_WEBHOOK_SECRET").encode()
    expected = "sha256=" + hmac.new(secret, raw_body, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, x_hub_signature_256 or ""):
        raise HTTPException(status_code=401, detail="Invalid Signature")

    payload = json.loads(raw_body)
    if x_github_event != "pull_request":
        return {"status": "ignored", "event": x_github_event}
    if payload.get("action") not in ("opened", "synchronize", "reopened"):
        return {"status": "ignored", "action": payload.get("action")}

    repo = payload["repository"]["full_name"]
    number = payload["number"]

    background_tasks.add_task(run_review, repo, number)
    return {"status": "queued", "repo": repo, "number": number}