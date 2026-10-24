import os
import re
import sys
from pathlib import Path
from typing import NamedTuple

ROOT = Path(__file__).resolve().parent.parent
HW1 = Path(os.environ.get("FUNNY_HW1", ROOT.parent / "hw1")).resolve()
SPEC = ROOT / "tokens.spec"
BUILD = ROOT / "build"
TABLE = BUILD / "dfa.json"


class Token(NamedTuple):
    kind: str
    lexeme: str
    line: int
    col: int
    offset: int

    def __str__(self):
        return f"{self.kind}({self.lexeme!r}, {self.line}, {self.col})"


class Diagnostic(NamedTuple):
    line: int
    col: int
    message: str

    def __str__(self):
        return f"{self.line}:{self.col}: {self.message}"


def _hw1():
    if not (HW1 / "funnylex").is_dir():
        raise RuntimeError(f"не найден лексер HW1 в {HW1} (укажите путь в FUNNY_HW1)")
    if str(HW1) not in sys.path:
        sys.path.insert(0, str(HW1))
    import funnylex.build
    import funnylex.lexer
    import funnylex.nfa
    return funnylex


def build_table(force: bool = False) -> Path:
    if force or not TABLE.exists() or TABLE.stat().st_mtime < SPEC.stat().st_mtime:
        fl = _hw1()
        fl.build.write_all(fl.build.build(str(SPEC)), str(BUILD))
    return TABLE


_cache = {}


def _lexer():
    if "lexer" not in _cache:
        fl = _hw1()
        _cache["lexer"] = fl.lexer.DFALexer.from_file(str(build_table()))
    return _cache["lexer"]


def token_names() -> dict:
    if "names" not in _cache:
        fl = _hw1()
        names = {"IDENT": "идентификатор", "INT": "число", "EOF": "конец файла"}
        for rule in fl.nfa.load_spec(str(SPEC)):
            if rule.name not in names and re.fullmatch(r"(?:\\.|[^\\\[\]()*+?|.^$])+", rule.regex):
                names[rule.name] = "'" + re.sub(r"\\(.)", r"\1", rule.regex) + "'"
        _cache["names"] = names
    return _cache["names"]


class Positions:
    def __init__(self, text: str):
        self.starts = [0] + [m.end() for m in re.finditer(r"\n", text)]

    def __call__(self, offset: int) -> tuple[int, int]:
        lo, hi = 0, len(self.starts) - 1
        while lo < hi:
            mid = (lo + hi + 1) // 2
            if self.starts[mid] <= offset:
                lo = mid
            else:
                hi = mid - 1
        return lo + 1, offset - self.starts[lo] + 1


def lex(text: str) -> tuple[list[Token], list[Diagnostic]]:
    pos = Positions(text)
    tokens, diags = [], []
    run_start, run_text, run_end = None, "", -1
    for t in _lexer().tokenize(text):
        line, col = pos(t.offset)
        if t.type == "ERROR" and t.error != "BAD_INT" and ord(t.lexeme[0]) > 127:
            if t.offset == run_end:
                run_text += t.lexeme
            else:
                if run_start is not None:
                    diags.append(Diagnostic(*run_start, f"лексическая ошибка: символы вне ASCII '{run_text}'"))
                run_start, run_text = (line, col), t.lexeme
            run_end = t.offset + len(t.lexeme)
            continue
        if t.type == "ERROR" and t.error == "BAD_INT":
            diags.append(Diagnostic(line, col, f"лексическая ошибка: неверное число '{t.lexeme}': "
                                               f"ведущие нули запрещены"))
            tokens.append(Token("INT", t.lexeme, line, col, t.offset))
            continue
        if t.type == "ERROR":
            diags.append(Diagnostic(line, col, f"лексическая ошибка: неожиданный символ {t.lexeme!r}"))
            continue
        tokens.append(Token(t.type, t.lexeme, line, col, t.offset))
    if run_start is not None:
        diags.append(Diagnostic(*run_start, f"лексическая ошибка: символы вне ASCII '{run_text}'"))
    line, col = pos(len(text))
    tokens.append(Token("EOF", "", line, col, len(text)))
    return tokens, sorted(diags, key=lambda d: (d.line, d.col))
