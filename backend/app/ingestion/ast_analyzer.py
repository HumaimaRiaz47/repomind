import ast


def analyze_python_file(file_path: str) -> dict:
    """
    Analyze a Python file using Python's built-in AST parser.
    """

    with open(
        file_path,
        "r",
        encoding="utf-8"
    ) as file:
        source_code = file.read()

    tree = ast.parse(source_code)

    functions = []
    classes = []
    imports = []
    calls = []
    exception_handlers = []

    for node in ast.walk(tree):

        # Functions
        if isinstance(
            node,
            (ast.FunctionDef, ast.AsyncFunctionDef)
        ):
            functions.append({
                "name": node.name,
                "line": node.lineno,
                "args": [
                    arg.arg
                    for arg in node.args.args
                ]
            })

        # Classes
        elif isinstance(node, ast.ClassDef):
            classes.append({
                "name": node.name,
                "line": node.lineno
            })

        # Imports
        elif isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(alias.name)

        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""

            for alias in node.names:
                imports.append(
                    f"{module}.{alias.name}"
                )

        # Function/method calls
        elif isinstance(node, ast.Call):

            if isinstance(node.func, ast.Name):
                calls.append(node.func.id)

            elif isinstance(node.func, ast.Attribute):
                calls.append(node.func.attr)

        # Exception handling
        elif isinstance(node, ast.ExceptHandler):
            exception_handlers.append({
                "line": node.lineno,
                "exception": (
                    ast.unparse(node.type)
                    if node.type
                    else "Exception"
                )
            })

    return {
        "file": file_path,
        "functions": functions,
        "classes": classes,
        "imports": imports,
        "calls": calls,
        "exception_handlers": exception_handlers,
    }