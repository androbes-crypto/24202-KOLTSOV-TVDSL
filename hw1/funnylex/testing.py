import json

from .lexer import DFALexer


class CaseError(ValueError):
    pass


def show(s: str) -> str:
    return json.dumps(s)


class Result:
    def __init__(self, kind, name, ok, detail=""):
        self.kind, self.name, self.ok, self.detail = kind, name, ok, detail


def _match(lexer, text, expect, trap):
    got, trapped = lexer.match(text)
    ok = got == expect and (trap is None or trapped == trap)
    return ok, "" if ok else f"ожидалось {expect} trap={trap}, получено {got} trap={trapped}"


def _lex(lexer, text, expect):
    got = [[t.type, t.lexeme] for t in lexer.tokenize(text)]
    ok = got == expect
    return ok, "" if ok else "получено: " + json.dumps(got)


def run_file(path: str, lexer: DFALexer) -> list[Result]:
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    unknown = set(data) - {"match", "lex", "chars"}
    if unknown:
        raise CaseError(f"{path}: неизвестные разделы {sorted(unknown)}")
    results = []
    for case in data.get("match", []):
        ok, detail = _match(lexer, case["input"], case["expect"], case.get("trap"))
        results.append(Result("match", f'{show(case["input"])} -> {case["expect"]}', ok, detail))
    for case in data.get("lex", []):
        ok, detail = _lex(lexer, case["input"], case["tokens"])
        name = show(case["input"])
        results.append(Result("lex", name if len(name) <= 50 else name[:47] + '..."', ok, detail))
    codes = []
    for case in data.get("chars", []):
        ch, expect = case["char"], case["expect"]
        if len(ch) != 1 or ord(ch) != case["code"]:
            raise CaseError(f"{path}: char не совпадает с code {case['code']}")
        codes.append(case["code"])
        if expect == "ERROR":
            ok1, d1 = _match(lexer, ch, None, case["trap"])
            ok2, d2 = _lex(lexer, ch, [["ERROR", ch]])
        else:
            ok1, d1 = _match(lexer, ch, expect, case["trap"])
            ok2, d2 = _lex(lexer, ch, [] if lexer.kind.get(expect) == "skip" else [[expect, ch]])
        results.append(Result("char", f'code {case["code"]:>6} {show(ch)} -> {expect}', ok1 and ok2,
                              "; ".join(d for d in (d1, d2) if d)))
    if codes:
        missing = sorted(set(range(128)) - set(codes))
        if missing or len(codes) != len(set(codes)):
            raise CaseError(f"{path}: каждый ASCII-код 0..127 должен встречаться ровно один раз, "
                            f"нет: {missing}")
    return results
