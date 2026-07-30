import os
from symbols import symbols_in_diff                 

def find_definition(folder, symbol):
    hits = []
    for root, dirs, files in os.walk(folder):
        for name in files:
            if not name.endswith(".py"):
                continue
            path = os.path.join(root, name)
            text = open(path, encoding="utf-8", errors="ignore").read()
            if f"def {symbol}" in text or f"class {symbol}" in text:
                hits.append(path)
    return hits

def repo_context(diff_text, folder):
    names = symbols_in_diff(diff_text)         
    lines = []                                  
    for name in names:                          
        hits = find_definition(folder, name)    
        if not hits:                            
            lines.append(f"- {name}: NOT FOUND in the repository")
        else:
            lines.append(f"- {name}: defined in {hits}")
    return "\n".join(lines)    

if __name__ == "__main__":
    diff = "--- a/x.py\n+++ b/x.py\n+    x = clone_pr(a, b)\n+    y = does_not_exist_xyz(1)\n"
    print(repo_context(diff, "."))