"""
code_parser.py
==============
Parses Python source files using the built-in `ast` module to extract
function-level metadata — names, arguments, docstrings, and raw source
code. The output is used by the ingestion pipeline to build chunks that
are embedded and stored in the vector store.
"""

import ast
import os


# ---------------------------------------------------------------------------
# 1. parse_file — extract every function from a Python source file
# ---------------------------------------------------------------------------

def parse_file(filepath: str) -> list[dict]:
    """
    Parse a Python file and extract metadata for every function and
    async function defined in it.

    Args:
        filepath: Absolute or relative path to a .py file.

    Returns:
        A list of dicts, one per function, each containing:
            name, args, docstring, body_text, start_line, end_line, file
    """
    filepath = os.path.normpath(filepath)
    print(f"\n[code_parser] Parsing file: {filepath}")

    # Read the raw source — we need it for line-slicing later
    with open(filepath, "r", encoding="utf-8") as f:
        source = f.read()

    source_lines = source.splitlines()

    # Build the AST
    try:
        tree = ast.parse(source, filename=filepath)
    except SyntaxError as exc:
        print(f"[code_parser] ✗ SyntaxError in {filepath}: {exc}")
        return []

    functions: list[dict] = []

    # Walk every node and pick up function definitions
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue

        # --- Function name -------------------------------------------------
        name = node.name

        # --- Argument names ------------------------------------------------
        args = [arg.arg for arg in node.args.args]

        # --- Docstring (first body expr if it's a constant string) ---------
        docstring = ast.get_docstring(node) or ""

        # --- Raw source lines of the function body ------------------------
        start_line = node.lineno            # 1-indexed
        end_line = node.end_lineno or start_line
        body_text = "\n".join(source_lines[start_line - 1 : end_line])

        # --- Build the result dict -----------------------------------------
        func_dict = {
            "name": name,
            "args": args,
            "docstring": docstring,
            "body_text": body_text,
            "start_line": start_line,
            "end_line": end_line,
            "file": filepath,
        }

        functions.append(func_dict)
        print(f"[code_parser]   ✓ Found function: {name}()  (lines {start_line}–{end_line})")

    print(f"[code_parser] Total functions extracted: {len(functions)}")
    return functions


# ---------------------------------------------------------------------------
# 2. build_chunk_text — format a function dict into an embeddable string
# ---------------------------------------------------------------------------

def build_chunk_text(func_dict: dict) -> str:
    """
    Convert a function metadata dict into a single formatted text
    block suitable for embedding and vector storage.

    Args:
        func_dict: A dict produced by parse_file().

    Returns:
        A human-readable string containing the function's name, file,
        location, arguments, docstring, and full source code.
    """
    args_str = ", ".join(func_dict["args"]) if func_dict["args"] else "(none)"
    docstring = func_dict["docstring"] or "(no docstring)"

    chunk = (
        f"Function: {func_dict['name']}\n"
        f"File: {func_dict['file']}\n"
        f"Line: {func_dict['start_line']}\n"
        f"Args: {args_str}\n"
        f"Docstring: {docstring}\n"
        f"Code:\n{func_dict['body_text']}"
    )
    return chunk


# ---------------------------------------------------------------------------
# 3. extract_imports — list all imports in a Python file
# ---------------------------------------------------------------------------

def extract_imports(filepath: str) -> list[str]:
    """
    Parse a Python file and return a flat list of all imported module
    names (both `import X` and `from X import Y` forms).

    Args:
        filepath: Path to a .py file.

    Returns:
        A deduplicated list of imported module/name strings.
    """
    filepath = os.path.normpath(filepath)

    with open(filepath, "r", encoding="utf-8") as f:
        source = f.read()

    try:
        tree = ast.parse(source, filename=filepath)
    except SyntaxError as exc:
        print(f"[code_parser] ✗ SyntaxError while extracting imports: {exc}")
        return []

    imports: list[str] = []

    for node in ast.walk(tree):
        # import X, import X as Y
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(alias.name)

        # from X import Y, from X import Y as Z
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            for alias in node.names:
                full_name = f"{module}.{alias.name}" if module else alias.name
                imports.append(full_name)

    # Deduplicate while preserving order
    seen = set()
    unique_imports = []
    for name in imports:
        if name not in seen:
            seen.add(name)
            unique_imports.append(name)

    print(f"[code_parser] Imports in {os.path.basename(filepath)}: {unique_imports}")
    return unique_imports


# ---------------------------------------------------------------------------
# Quick manual test
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import sys

    # Default to the sample code file if no argument given
    target = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
        os.path.dirname(__file__), "..", "sample_data", "sample_code.py"
    )

    print("=" * 60)
    print("  Code Parser — Manual Test")
    print("=" * 60)

    # --- Parse functions ---------------------------------------------------
    funcs = parse_file(target)

    print("\n--- Chunk previews ---\n")
    for fd in funcs:
        chunk = build_chunk_text(fd)
        # Print first 300 chars of each chunk for a quick preview
        print(chunk[:300])
        print("…\n" + "-" * 40)

    # --- Extract imports ---------------------------------------------------
    print("\n--- Imports ---")
    imps = extract_imports(target)
    for imp in imps:
        print(f"  • {imp}")
