import random

from .lexer import ROOT, Token, lex
from .nodes import dumps, to_text
from .parser import ParserLoop, parse, parse_tokens

TESTS = ROOT / "tests"


class Result:
    def __init__(self, group, name, ok, detail=""):
        self.group = group
        self.name = name
        self.ok = ok
        self.detail = detail


def _diff(expected, got):
    exp = expected.splitlines()
    out = got.splitlines()
    for n, (a, b) in enumerate(zip(exp, out), 1):
        if a != b:
            return f"строка {n}:\n        ожидалось: {a}\n        получено:  {b}"
    return f"разная длина: ожидалось {len(exp)} строк, получено {len(out)}"


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
        text = "".join(f"{line}\n" for line in case["program"])
        case["text"] = text.replace("\n", "\r\n") if case["name"].endswith("[crlf]") else text
    return cases


def save_cases(path, cases):
    blocks = []
    for case in cases:
        program = "".join(f"{line}\n" for line in case["program"])
        expected = "".join(f"{line}\n" for line in case["expected"])
        blocks.append(f"=== {case['name']}\n{program}--- ожидается\n{expected}")
    path.write_text("\n".join(blocks), encoding="utf-8")


def run_snapshots(update=False):
    results = []
    for group, filename in (("ok", "positive.txt"), ("err", "negative.txt")):
        path = TESTS / filename
        cases = load_cases(path)
        for case in cases:
            ast, diags = parse(case["text"])
            dumps(ast)
            got = to_text(ast) if group == "ok" else "".join(f"{d}\n" for d in diags)
            expected = "".join(f"{line}\n" for line in case["expected"])
            if update:
                case["expected"] = got.splitlines()
                expected = got
            if group == "ok" and diags:
                results.append(Result(group, case["name"], False,
                                      "неожиданные ошибки: " + "; ".join(map(str, diags))))
            elif group == "err" and not diags:
                results.append(Result(group, case["name"], False, "ожидались ошибки, а разбор прошёл"))
            else:
                results.append(Result(group, case["name"], expected == got,
                                      "" if expected == got else _diff(expected, got)))
        if update:
            save_cases(path, cases)
    return results


# Портим корректные программы (удаляем, вставляем, переставляем токены) и проверяем,
# что парсер на них не зацикливается и не падает.
def run_fuzz(count=2000, seed=2026):
    rnd = random.Random(seed)
    corpus = []
    for case in load_cases(TESTS / "positive.txt"):
        tokens = lex(case["text"])[0][:-1]  # без EOF
        if tokens:
            corpus.append(tokens)
    pool = [t for tokens in corpus for t in tokens]

    for n in range(count):
        toks = list(rnd.choice(corpus))
        for _ in range(rnd.randint(1, 6)):
            k = rnd.randrange(len(toks) + 1)
            action = rnd.random()
            if action < 0.4 and toks:
                del toks[min(k, len(toks) - 1)]
            elif action < 0.8:
                toks.insert(k, rnd.choice(pool))
            elif toks:
                j = rnd.randrange(len(toks))
                toks[j], toks[k - 1] = toks[k - 1], toks[j]
        if n % 10 == 0:
            # иногда — просто случайный набор токенов
            toks = [rnd.choice(pool) for _ in range(rnd.randint(0, 60))]
        line = toks[-1].line if toks else 1
        col = toks[-1].col + 1 if toks else 1
        toks.append(Token("EOF", "", line, col, 0))
        try:
            parse_tokens(toks, [])
        except ParserLoop:
            return Result("fuzz", "без зацикливания", False, f"зацикливание на варианте {n}")
        except RecursionError:
            return Result("fuzz", "без зацикливания", False, f"слишком глубокая рекурсия на варианте {n}")
    return Result("fuzz", f"{count} испорченных программ без зацикливания", True)
