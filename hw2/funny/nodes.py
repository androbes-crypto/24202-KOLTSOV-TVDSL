import json


class Node:
    # at — токен, по которому берётся позиция узла
    def __init__(self, kind, at, **fields):
        self.kind = kind
        if at is not None:
            self.line = at.line
            self.col = at.col
        else:
            self.line = 0
            self.col = 0
        self.fields = fields

    # поля узла доступны как атрибуты: node.left, node.body
    def __getattr__(self, name):
        try:
            return self.fields[name]
        except KeyError:
            raise AttributeError(name)

    def to_json(self):
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


def dumps(node):
    return json.dumps(node.to_json(), ensure_ascii=False, indent=2)


def to_text(node):
    lines = []
    _text(node, 0, lines)
    return "\n".join(lines) + "\n"


def _scalar(v):
    if isinstance(v, str):
        return json.dumps(v, ensure_ascii=False)
    if isinstance(v, bool):
        return str(v).lower()
    return str(v)


def _text(node, depth, lines):
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
