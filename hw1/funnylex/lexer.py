import json
from typing import NamedTuple, Optional


class Token(NamedTuple):
    type: str
    lexeme: str
    offset: int
    error: Optional[str] = None


class DFALexer:
    def __init__(self, table: dict):
        if table.get("format") != "funny-dfa/1":
            raise ValueError("unsupported table format")
        self.delta = table["transitions"]
        self.start = table["start"]
        self.trap = table["trap"]
        self.char_to_class = table["classes"]["char_to_class"]
        self.non_ascii = table["classes"]["non_ascii_class"]
        self.accept = [st["accept"] for st in table["states"]]
        self.kind = {t["name"]: t["kind"] for t in table["tokens"]}

    @classmethod
    def from_file(cls, path: str) -> "DFALexer":
        with open(path, encoding="utf-8") as f:
            return cls(json.load(f))

    def symbol(self, ch: str) -> int:
        o = ord(ch)
        return self.char_to_class[o] if o < 128 else self.non_ascii

    def match(self, text: str) -> tuple[Optional[str], bool]:
        s = self.start
        for ch in text:
            s = self.delta[s][self.symbol(ch)]
            if s == self.trap:
                return None, True
        return self.accept[s], False

    def tokenize(self, text: str, keep_skip: bool = False) -> list[Token]:
        out, i, n = [], 0, len(text)
        while i < n:
            s, j, last = self.start, i, None
            while j < n:
                s = self.delta[s][self.symbol(text[j])]
                if s == self.trap:
                    break
                j += 1
                if self.accept[s] is not None:
                    last = (j, self.accept[s])
            if last is None:
                ch = text[i]
                why = "non-ASCII character" if ord(ch) > 127 else "unexpected character"
                out.append(Token("ERROR", ch, i, why))
                i += 1
                continue
            j, name = last
            kind = self.kind[name]
            if kind == "error":
                out.append(Token("ERROR", text[i:j], i, name))
            elif kind == "token" or keep_skip:
                out.append(Token(name, text[i:j], i))
            i = j
        return out
