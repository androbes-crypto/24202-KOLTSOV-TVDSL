import random
import time
from pathlib import Path

from .lexer import ROOT, lex
from .nodes import dumps, to_text
from .parser import ParserLoop, parse, parse_tokens

TESTS = ROOT / "tests"


class Result:
    def __init__(self, group, name, ok, detail=""):
        self.group, self.name, self.ok, self.detail = group, name, ok, detail


def _diff(expected: str, got: str) -> str:
    exp, out = expected.splitlines(), got.splitlines()
    for n, (a, b) in enumerate(zip(exp, out), 1):
        if a != b:
            return f"строка {n}:\n        ожидалось: {a}\n        получено:  {b}"
    return f"разная длина: ожидалось {len(exp)} строк, получено {len(out)}"


def load_cases(path: Path) -> list[dict]:
    cases, current, section = [], None, None
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


def save_cases(path: Path, cases: list[dict]):
    blocks = []
    for case in cases:
        program = "".join(f"{line}\n" for line in case["program"])
        expected = "".join(f"{line}\n" for line in case["expected"])
        blocks.append(f"=== {case['name']}\n{program}--- ожидается\n{expected}")
    path.write_text("\n".join(blocks), encoding="utf-8")


def run_snapshots(update: bool = False) -> list[Result]:
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


def run_fuzz(count: int = 2000, seed: int = 2026) -> Result:
    rnd = random.Random(seed)
    corpus = [lex(c["text"])[0][:-1] for c in load_cases(TESTS / "positive.txt")]
    corpus = [toks for toks in corpus if toks]
    pool = [t for toks in corpus for t in toks]
    worst, started = 0.0, time.perf_counter()
    for n in range(count):
        toks = list(rnd.choice(corpus))
        for _ in range(rnd.randint(1, 6)):
            op = rnd.random()
            k = rnd.randrange(len(toks) + 1)
            if op < 0.4 and toks:
                del toks[min(k, len(toks) - 1)]
            elif op < 0.8:
                toks.insert(k, rnd.choice(pool))
            elif toks:
                j = rnd.randrange(len(toks))
                toks[j], toks[k - 1] = toks[k - 1], toks[j]
        if n % 10 == 0:
            toks = [rnd.choice(pool) for _ in range(rnd.randint(0, 60))]
        eof = toks[-1] if toks else None
        toks.append(type(pool[0])("EOF", "", eof.line if eof else 1, eof.col + 1 if eof else 1, 0))
        t0 = time.perf_counter()
        try:
            parse_tokens(toks, [])
        except ParserLoop:
            return Result("fuzz", "без зацикливания", False, f"зацикливание на варианте {n}")
        except RecursionError:
            return Result("fuzz", "без зацикливания", False, f"слишком глубокая рекурсия на варианте {n}")
        worst = max(worst, time.perf_counter() - t0)
    total = time.perf_counter() - started
    return Result("fuzz", f"{count} испорченных программ без зацикливания", True,
                  f"всего {total:.2f} c, худший разбор {worst * 1000:.1f} мс")
