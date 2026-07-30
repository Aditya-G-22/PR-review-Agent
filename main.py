import os
import requests
import hmac, hashlib, json
import shutil
from clone import clone_pr
from search import repo_context
from dotenv import load_dotenv
from collections import defaultdict
from fastapi import FastAPI, Header, Request, HTTPException, BackgroundTasks
from review import review_with_confidence, is_confident

load_dotenv()

app = FastAPI()

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
        finally:
            shutil.rmtree(folder, ignore_errors=True)

        print(f"[background] DONE review for {repo} PR #{number}")
    except Exception as e:
        print(f"[background] review FAILED for {repo} PR #{number}: {e}")


@app.get("/health")
def health():
    return {"status": "ok"}

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