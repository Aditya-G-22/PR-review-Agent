import tempfile
import subprocess

def clone_pr(repo, sha) :
    folder = tempfile.mkdtemp()
    subprocess.run(["git", "init"], cwd = folder, check = True)
    subprocess.run(["git", "remote", "add", "origin", f"https://github.com/{repo}.git"], cwd=folder, check=True)
    subprocess.run(["git", "fetch", "--depth", "1", "origin", sha], cwd=folder, check=True)   
    subprocess.run(["git", "checkout", "FETCH_HEAD"], cwd=folder, check=True)
    return folder