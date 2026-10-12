ASCII = frozenset(range(128))
_ESCAPES = {"n": 10, "t": 9, "r": 13, "0": 0, "f": 12, "v": 11}
_DIGITS = frozenset(range(ord("0"), ord("9") + 1))
_WORD = _DIGITS | frozenset(range(65, 91)) | frozenset(range(97, 123)) | {ord("_")}
_SPACE = frozenset({32, 9, 10, 11, 12, 13})


class RegexError(ValueError):
    pass


class _Parser:
    def __init__(self, src: str):
        self.src = src
        self.i = 0

    def peek(self):
        return self.src[self.i] if self.i < len(self.src) else None

    def take(self):
        c = self.peek()
        if c is None:
            raise self.err("unexpected end of regex")
        self.i += 1
        return c

    def err(self, msg):
        return RegexError(f"{msg} at position {self.i} in /{self.src}/")

    def parse(self):
        node = self.alt()
        if self.i != len(self.src):
            raise self.err(f"unexpected {self.peek()!r}")
        return node

    def alt(self):
        node = self.concat()
        while self.peek() == "|":
            self.i += 1
            node = ("alt", node, self.concat())
        return node

    def concat(self):
        parts = []
        while self.peek() not in (None, "|", ")"):
            parts.append(self.repeat())
        if not parts:
            return ("eps",)
        node = parts[0]
        for p in parts[1:]:
            node = ("cat", node, p)
        return node

    def repeat(self):
        node = self.atom()
        while self.peek() in ("*", "+", "?"):
            op = self.take()
            node = ({"*": "star", "+": "plus", "?": "opt"}[op], node)
        return node

    def atom(self):
        c = self.take()
        if c == "(":
            node = self.alt()
            if self.peek() != ")":
                raise self.err("expected ')'")
            self.i += 1
            return node
        if c == "[":
            return ("set", self.char_class())
        if c == ".":
            return ("set", ASCII - {10})
        if c == "\\":
            return ("set", self.escape())
        if c in "*+?":
            raise self.err(f"nothing to repeat before {c!r}")
        return ("set", self.literal(c))

    def literal(self, c):
        if ord(c) > 127:
            raise self.err(f"non-ASCII character {c!r} in regex")
        return frozenset([ord(c)])

    def escape(self):
        c = self.take()
        if c in _ESCAPES:
            return frozenset([_ESCAPES[c]])
        if c == "x":
            h = self.src[self.i:self.i + 2]
            try:
                v = int(h, 16)
            except ValueError:
                raise self.err("bad \\xHH escape")
            if len(h) != 2 or v > 127:
                raise self.err("\\xHH must be ASCII")
            self.i += 2
            return frozenset([v])
        if c == "d":
            return _DIGITS
        if c == "w":
            return _WORD
        if c == "s":
            return _SPACE
        if c.isalnum():
            raise self.err(f"unknown escape \\{c}")
        return self.literal(c)

    def char_class(self):
        negate = False
        if self.peek() == "^":
            negate = True
            self.i += 1
        chars = set()
        first = True
        while True:
            c = self.peek()
            if c is None:
                raise self.err("unterminated '['")
            if c == "]" and not first:
                self.i += 1
                break
            self.i += 1
            first = False
            lo = self.escape() if c == "\\" else self.literal(c)
            nxt = self.src[self.i + 1] if self.i + 1 < len(self.src) else None
            if self.peek() == "-" and nxt is not None and nxt != "]":
                self.i += 1
                c2 = self.take()
                hi = self.escape() if c2 == "\\" else self.literal(c2)
                if len(lo) != 1 or len(hi) != 1:
                    raise self.err("bad range in character class")
                a, b = min(lo), min(hi)
                if a > b:
                    raise self.err("reversed range in character class")
                chars.update(range(a, b + 1))
            else:
                chars.update(lo)
        s = frozenset(chars)
        return ASCII - s if negate else s


def parse_regex(src: str):
    return _Parser(src).parse()


def describe_chars(codes) -> str:
    def show(c):
        names = {9: "\\t", 10: "\\n", 13: "\\r", 32: "SP", 92: "\\\\"}
        if c in names:
            return names[c]
        if 33 <= c < 127:
            return chr(c)
        return f"\\x{c:02X}"

    codes = sorted(codes)
    parts, i = [], 0
    while i < len(codes):
        j = i
        while j + 1 < len(codes) and codes[j + 1] == codes[j] + 1:
            j += 1
        if j - i >= 2:
            parts.append(f"{show(codes[i])}-{show(codes[j])}")
        else:
            parts.extend(show(c) for c in codes[i:j + 1])
        i = j + 1
    return "".join(parts) if all(len(p) == 1 for p in parts) else " ".join(parts)
