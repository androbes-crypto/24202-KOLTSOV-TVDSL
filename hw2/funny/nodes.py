import json


class Node:
    __slots__ = ("kind", "line", "col", "fields")

    def __init__(self, kind: str, at, **fields):
        self.kind = kind
        self.line, self.col = (at.line, at.col) if at is not None else (0, 0)
        self.fields = fields

    def __getattr__(self, name):
        try:
            return self.fields[name]
        except KeyError:
            raise AttributeError(name)

    def to_json(self) -> dict:
        out = {"kind": self.kind, "line": self.line, "col": self.col}
        for k, v in self.fields.items():
            out[k] = _json(v)
        return out

    def __repr__(self):
        return f"Node({self.kind}@{self.line}:{self.col})"


def _json(v):
    if isinstance(v, Node):
        return v.to_json()
    if isinstance(v, list):
        return [_json(x) for x in v]
    return v


def dumps(node: Node) -> str:
    return json.dumps(node.to_json(), ensure_ascii=False, indent=2)


def to_text(node: Node) -> str:
    lines = []
    _text(node, 0, lines)
    return "\n".join(lines) + "\n"


def _scalar(v) -> str:
    return json.dumps(v, ensure_ascii=False) if isinstance(v, str) else str(v).lower() if isinstance(v, bool) else str(v)


def _text(node: Node, depth: int, lines: list):
    pad = "  " * depth
    attrs = " ".join(f"{k}={_scalar(v)}" for k, v in node.fields.items()
                     if not isinstance(v, (Node, list)) and v is not None)
    lines.append(f"{pad}{node.kind}{' ' + attrs if attrs else ''} @{node.line}:{node.col}")
    for k, v in node.fields.items():
        if isinstance(v, Node):
            lines.append(f"{pad}  {k}:")
            _text(v, depth + 2, lines)
        elif isinstance(v, list):
            lines.append(f"{pad}  {k}:{'' if v else ' []'}")
            for x in v:
                _text(x, depth + 2, lines)
