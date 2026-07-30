import re

def symbols_in_diff(diff_text) :
    names = set()

    for line in diff_text.split("\n") :
        if line.startswith(("+++", "---")) :
            continue
        if line.startswith(("+", "-")) :
            names.update(re.findall(r"(\w+)\s*\(", line))
    return names 

if __name__ == "__main__":
    diff = "--- a/x.py\n+++ b/x.py\n+    user = get_user_by_id(request.args)\n-    user = get_user(x)\n"
    print(symbols_in_diff(diff))