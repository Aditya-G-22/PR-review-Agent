def number_diff(diff_text) :
    new_line = 0
    output = []

    for line in diff_text.split("\n") :

        if line.startswith(("diff ", "index ", "---", "+++")) :
            output.append(line)
            continue

        if line.startswith("@@") :
            new_line = int(line.split(" ")[2][1:].split(",")[0])
            output.append(line)
            continue

        if line.startswith("-") :
            output.append(line)
            continue

        output.append(f"{new_line}: {line}")
        new_line += 1

    return "\n".join(output)

def diff_line_map(diff_text):
    line_map = {}          # file path -> set of valid new-file line numbers
    current_file = None
    new_line = 0
    for line in diff_text.split("\n"):
        if line.startswith("+++ "):
            current_file = line[6:]          # "+++ b/app/users.py" -> "app/users.py"
            line_map[current_file] = set()
            continue
        if line.startswith(("diff ", "index ", "--- ")):
            continue
        if line.startswith("@@"):
            new_line = int(line.split(" ")[2][1:].split(",")[0])
            continue
        if line.startswith("-"):
            continue
        if current_file is not None:
            line_map[current_file].add(new_line)
        new_line += 1
    return line_map

if __name__ == "__main__" :
    sample_diff = """diff --git a/Rust.gitignore b/Rust.gitignore
    index ad67955886..c3ec7d27c1 100644
    --- a/Rust.gitignore
    +++ b/Rust.gitignore
    @@ -13,6 +13,9 @@ target
    # Contains mutation testing data
    **/mutants.out*/

    +# rustc will dump stack traces when hitting an internal compiler error to PWD
    +rustc-ice-*.txt
    +
    # RustRover
    """

    print(number_diff(sample_diff))