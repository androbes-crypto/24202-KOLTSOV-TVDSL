from dataclasses import dataclass

from .regex import parse_regex

KINDS = ("token", "skip", "error")


@dataclass
class TokenRule:
    name: str
    kind: str
    regex: str
    priority: int


def load_spec(path: str) -> list[TokenRule]:
    rules = []
    with open(path, encoding="utf-8") as f:
        for lineno, raw in enumerate(f, 1):
            line = raw.rstrip("\r\n")
            if not line.strip() or line.lstrip().startswith("#"):
                continue
            parts = line.split(None, 2)
            if len(parts) != 3:
                raise ValueError(f"{path}:{lineno}: expected 'NAME KIND REGEX'")
            name, kind, regex = parts[0], parts[1], parts[2].strip()
            if kind not in KINDS:
                raise ValueError(f"{path}:{lineno}: kind must be one of {KINDS}")
            if any(r.name == name for r in rules):
                raise ValueError(f"{path}:{lineno}: duplicate token {name}")
            rules.append(TokenRule(name, kind, regex, len(rules)))
    if not rules:
        raise ValueError(f"{path}: no token rules")
    return rules


class NFA:

    def __init__(self):
        self.eps: list[list[int]] = []
        self.edges: list[list[tuple[frozenset, int]]] = []
        self.start = None
        self.accept: dict[int, int] = {}

    def new_state(self) -> int:
        self.eps.append([])
        self.edges.append([])
        return len(self.eps) - 1

    @property
    def size(self) -> int:
        return len(self.eps)

    def fragment(self, node) -> tuple[int, int]:
        kind = node[0]
        if kind == "eps":
            s, e = self.new_state(), self.new_state()
            self.eps[s].append(e)
            return s, e
        if kind == "set":
            s, e = self.new_state(), self.new_state()
            self.edges[s].append((node[1], e))
            return s, e
        if kind == "cat":
            s1, e1 = self.fragment(node[1])
            s2, e2 = self.fragment(node[2])
            self.eps[e1].append(s2)
            return s1, e2
        if kind == "alt":
            s, e = self.new_state(), self.new_state()
            s1, e1 = self.fragment(node[1])
            s2, e2 = self.fragment(node[2])
            self.eps[s] += [s1, s2]
            self.eps[e1].append(e)
            self.eps[e2].append(e)
            return s, e
        if kind == "star":
            s, e = self.new_state(), self.new_state()
            s1, e1 = self.fragment(node[1])
            self.eps[s] += [s1, e]
            self.eps[e1] += [s1, e]
            return s, e
        if kind == "plus":
            return self.fragment(("cat", node[1], ("star", node[1])))
        if kind == "opt":
            return self.fragment(("alt", node[1], ("eps",)))
        raise ValueError(f"unknown AST node {kind}")


def build_nfa(rules: list[TokenRule]) -> tuple[NFA, dict[str, int]]:
    nfa = NFA()
    nfa.start = nfa.new_state()
    sizes = {}
    for rule in rules:
        before = nfa.size
        s, e = nfa.fragment(parse_regex(rule.regex))
        sizes[rule.name] = nfa.size - before
        nfa.eps[nfa.start].append(s)
        nfa.accept[e] = rule.priority
    return nfa, sizes
