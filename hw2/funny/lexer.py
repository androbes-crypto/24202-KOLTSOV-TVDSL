# Подключение лексера из HW1: таблица ДКА строится по tokens.spec, токены получают строку и столбец.
import os
import sys
from pathlib import Path
from typing import NamedTuple

ROOT = Path(__file__).resolve().parent.parent
HW1 = Path(os.environ.get("FUNNY_HW1", ROOT.parent / "hw1")).resolve()
SPEC = ROOT / "tokens.spec"
BUILD = ROOT / "build"
TABLE = BUILD / "dfa.json"

if not (HW1 / "funnylex").is_dir():
    raise RuntimeError(f"не найден лексер HW1 в {HW1} (укажите путь в FUNNY_HW1)")
if str(HW1) not in sys.path:
    sys.path.insert(0, str(HW1))

import funnylex.build
from funnylex.lexer import DFALexer

# как показывать токены в сообщениях об ошибках
TOKEN_NAMES = {
    "IDENT": "идентификатор",
    "INT": "число",
    "EOF": "конец файла",
    "KW_FUNCTION": "'function'",
    "KW_RETURNS": "'returns'",
    "KW_REQUIRES": "'requires'",
    "KW_ENSURES": "'ensures'",
    "KW_VAR": "'var'",
    "KW_WHILE": "'while'",
    "KW_IF": "'if'",
    "KW_ELSE": "'else'",
    "KW_ASSERT": "'assert'",
    "KW_ASSUME": "'assume'",
    "KW_INVARIANT": "'invariant'",
    "KW_LENGTH": "'length'",
    "KW_INT": "'int'",
    "KW_BOOL": "'bool'",
    "KW_TRUE": "'true'",
    "KW_FALSE": "'false'",
    "EQ": "'=='",
    "NE": "'!='",
    "LE": "'<='",
    "GE": "'>='",
    "LT": "'<'",
    "GT": "'>'",
    "ASSIGN": "'='",
    "AND": "'&&'",
    "OR": "'||'",
    "NOT": "'!'",
    "PLUS": "'+'",
    "MINUS": "'-'",
    "STAR": "'*'",
    "SLASH": "'/'",
    "PERCENT": "'%'",
    "LPAREN": "'('",
    "RPAREN": "')'",
    "LBRACKET": "'['",
    "RBRACKET": "']'",
    "LBRACE": "'{'",
    "RBRACE": "'}'",
    "COMMA": "','",
    "SEMI": "';'",
    "COLON": "':'",
}


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


def build_table(force=False):
    # пересобираем таблицу, если её нет или tokens.spec новее
    if force or not TABLE.exists() or TABLE.stat().st_mtime < SPEC.stat().st_mtime:
        result = funnylex.build.build(str(SPEC))
        funnylex.build.write_all(result, str(BUILD))
    return TABLE


lexer = None


def get_lexer():
    global lexer
    if lexer is None:
        lexer = DFALexer.from_file(str(build_table()))
    return lexer


def position(text, offset):
    # строка и столбец считаются с 1
    line = text.count("\n", 0, offset) + 1
    line_start = text.rfind("\n", 0, offset) + 1
    return line, offset - line_start + 1


def lex(text):
    tokens = []
    diags = []
    # подряд идущие символы вне ASCII выдаём одной ошибкой
    bad_start = None
    bad_text = ""
    bad_end = -1

    for t in get_lexer().tokenize(text):
        line, col = position(text, t.offset)
        if t.type == "ERROR" and t.error != "BAD_INT" and ord(t.lexeme[0]) > 127:
            if t.offset == bad_end:
                bad_text += t.lexeme
            else:
                if bad_start is not None:
                    diags.append(Diagnostic(bad_start[0], bad_start[1],
                                            f"лексическая ошибка: символы вне ASCII '{bad_text}'"))
                bad_start = (line, col)
                bad_text = t.lexeme
            bad_end = t.offset + len(t.lexeme)
        elif t.type == "ERROR" and t.error == "BAD_INT":
            diags.append(Diagnostic(line, col, f"лексическая ошибка: неверное число '{t.lexeme}': "
                                               f"ведущие нули запрещены"))
            # парсеру всё равно отдаём число, чтобы не было лишних ошибок
            tokens.append(Token("INT", t.lexeme, line, col, t.offset))
        elif t.type == "ERROR":
            diags.append(Diagnostic(line, col, f"лексическая ошибка: неожиданный символ {t.lexeme!r}"))
        else:
            tokens.append(Token(t.type, t.lexeme, line, col, t.offset))

    if bad_start is not None:
        diags.append(Diagnostic(bad_start[0], bad_start[1], f"лексическая ошибка: символы вне ASCII '{bad_text}'"))
    line, col = position(text, len(text))
    tokens.append(Token("EOF", "", line, col, len(text)))
    diags.sort(key=lambda d: (d.line, d.col))
    return tokens, diags
