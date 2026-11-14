
from .checker import ROOT, check

TESTS = ROOT / "tests"
EXPR_KINDS = {"Int", "Bool", "Var", "Binary", "Unary", "Index", "Update", "Call", "Length"}


class Result:
    def __init__(self, group, name, ok, detail=""):
        self.group = group
        self.name = name
        self.ok = ok
        self.detail = detail


def load_cases(path):
    cases = []
    current = None
    section = None
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("=== "):
            current = {"name": line[4:].strip(), "program": [], "expected": []}
            cases.append(current)
            section = "program"
        elif line.startswith("--- ") and current is not None:
            section = "expected"
        elif current is not None:
            current[section].append(line)
    for case in cases:
        for key in ("program", "expected"):
            while case[key] and not case[key][-1].strip():
                case[key].pop()
        case["text"] = "".join(f"{line}\n" for line in case["program"])
    return cases


def save_cases(path, cases):
    blocks = []
    for case in cases:
        program = "".join(f"{line}\n" for line in case["program"])
        expected = "".join(f"{line}\n" for line in case["expected"])
        blocks.append(f"=== {case['name']}\n{program}--- ожидается\n{expected}")
    path.write_text("\n".join(blocks), encoding="utf-8")


# выражения без типа в аннотированном AST (их быть не должно)
def untyped_expressions(node, out=None):
    if out is None:
        out = []
    if hasattr(node, "kind"):
        if node.kind in EXPR_KINDS and node.fields.get("type") in (None, "?", "<ошибка>"):
            out.append(f"{node.kind}@{node.line}:{node.col}")
        for v in node.fields.values():
            untyped_expressions(v, out)
    elif isinstance(node, list):
        for x in node:
            untyped_expressions(x, out)
    return out


def _diff(expected, got):
    exp = expected.splitlines()
    out = got.splitlines()
    for n, (a, b) in enumerate(zip(exp, out), 1):
        if a != b:
            return f"строка {n}:\n        ожидалось: {a}\n        получено:  {b}"
    return f"разная длина: ожидалось {len(exp)} строк, получено {len(out)}:\n        " + "\n        ".join(out)


def run(update=False):
    results = []
    for group, filename in (("ok", "positive.txt"), ("err", "negative.txt")):
        path = TESTS / filename
        cases = load_cases(path)
        for case in cases:
            ast, diags, summary = check(case["text"])
            if group == "ok":
                got = "".join(f"{line}\n" for line in summary or [])
            else:
                got = "".join(f"{d}\n" for d in diags)
            expected = "".join(f"{line}\n" for line in case["expected"])
            if update:
                case["expected"] = got.splitlines()
                expected = got
            if group == "ok" and diags:
                results.append(Result(group, case["name"], False, "неожиданные ошибки: " + "; ".join(map(str, diags))))
            elif group == "ok" and untyped_expressions(ast):
                results.append(Result(group, case["name"], False,
                                      "выражения без типа: " + ", ".join(untyped_expressions(ast))))
            elif group == "err" and not diags:
                results.append(Result(group, case["name"], False, "ожидались ошибки, а проверка прошла"))
            elif group == "err" and summary is None:
                results.append(Result(group, case["name"], False,
                                      "синтаксическая ошибка вместо семантической: " + "; ".join(map(str, diags))))
            else:
                results.append(Result(group, case["name"], expected == got,
                                      "" if expected == got else _diff(expected, got)))
        if update:
            save_cases(path, cases)
    return results
