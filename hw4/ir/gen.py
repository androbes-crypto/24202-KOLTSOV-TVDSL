# Генерация TAC из аннотированного AST (HW3).
import os
import sys
from pathlib import Path

from .tac import Function, Instr

ROOT = Path(__file__).resolve().parent.parent
HW3 = Path(os.environ.get("FUNNY_HW3", ROOT.parent / "hw3")).resolve()
if not (HW3 / "sema").is_dir():
    raise RuntimeError(f"не найдена семантика HW3 в {HW3} (укажите путь в FUNNY_HW3)")
if str(HW3) not in sys.path:
    sys.path.insert(0, str(HW3))

from sema import check  # noqa: E402


class CompileError(Exception):
    def __init__(self, diagnostics):
        super().__init__("; ".join(map(str, diagnostics)))
        self.diagnostics = diagnostics


def pos(node):
    return f"{node.line}:{node.col}"


def find_decls(node, out):
    if isinstance(node, list):
        for x in node:
            find_decls(x, out)
    elif hasattr(node, "kind"):
        if node.kind == "VarDecl":
            out.append(node)
        for v in node.fields.values():
            find_decls(v, out)


class Generator:
    def __init__(self, fn_node):
        self.fn = fn_node
        self.names = {}     # (имя, позиция объявления) -> имя в IR
        self.types = {}
        self.temps = set()
        self.reserved = set()
        self.temp_no = 0
        self.label_no = 0
        self.code = []

    def declare(self, name, decl, type_):
        # одинаковые имена бывают только в соседних блоках: второе станет x#2
        ir_name = name
        n = 1
        while ir_name in self.types:
            n += 1
            ir_name = f"{name}#{n}"
        self.names[(name, decl)] = ir_name
        self.types[ir_name] = type_
        return ir_name

    def new_temp(self, type_):
        self.temp_no += 1
        while f"t{self.temp_no}" in self.reserved:
            self.temp_no += 1
        t = f"t{self.temp_no}"
        self.types[t] = type_
        self.temps.add(t)
        return t

    def new_labels(self, *kinds):
        self.label_no += 1
        return [f"L{self.label_no}_{k}" for k in kinds]

    def emit(self, op, **kw):
        self.code.append(Instr(op, **kw))

    def label(self, name):
        self.emit("label", target=name)

    def run(self):
        decls = []
        find_decls(self.fn.body, decls)
        self.reserved = {p.name for p in self.fn.params + self.fn.returns} | {d.name for d in decls}
        params = [(self.declare(p.name, pos(p), p.type), p.type) for p in self.fn.params]
        results = [(self.declare(r.name, pos(r), r.type), r.type) for r in self.fn.returns]
        for d in decls:
            self.declare(d.name, pos(d), d.type)
        self.stmt(self.fn.body)
        self.emit("return", args=[name for name, _ in results])
        f = Function(self.fn.name, params, results, self.types, self.temps)
        f.body = self.code
        return f

    def stmt(self, s):
        if s is None:
            return
        if s.kind == "Block":
            for x in s.stmts:
                self.stmt(x)
        elif s.kind == "VarDecl":
            if s.init is not None:
                self.expr_to(s.init, self.names[(s.name, pos(s))])
        elif s.kind == "Assign":
            # a[i] = v уже обессахарено в HW2: a = Update(a, i, v)
            self.expr_to(s.value, self.names[(s.target, s.decl)])
        elif s.kind == "If":
            self.gen_if(s)
        elif s.kind == "While":
            head, body, end = self.new_labels("while", "body", "end")
            self.label(head)
            self.cond(s.cond, body, end)
            self.label(body)
            self.stmt(s.body)
            self.emit("goto", target=head)
            self.label(end)
        elif s.kind == "Assert":
            self.emit("assert", args=[self.expr(s.cond)])
        elif s.kind == "Assume":
            pass  # assume нужен только для верификации
        elif s.kind == "CallStmt":
            args = [self.expr(a) for a in s.call.args]
            self.emit("call", func=s.call.name, args=args, dsts=[])
        else:
            raise ValueError("неизвестный оператор " + s.kind)

    def gen_if(self, s):
        if s.orelse is None:
            then, end = self.new_labels("then", "end")
            self.cond(s.cond, then, end)
            self.label(then)
            self.stmt(s.then)
        else:
            then, else_, end = self.new_labels("then", "else", "end")
            self.cond(s.cond, then, else_)
            self.label(then)
            self.stmt(s.then)
            self.emit("goto", target=end)
            self.label(else_)
            self.stmt(s.orelse)
        self.label(end)

    # условие как переходы: && и || вычисляются по короткой схеме
    def cond(self, e, yes, no):
        if e.kind == "Bool":
            self.emit("goto", target=yes if e.value else no)
        elif e.kind == "Unary" and e.op == "!":
            self.cond(e.operand, no, yes)
        elif e.kind == "Binary" and e.op == "&&":
            mid = self.new_labels("and")[0]
            self.cond(e.left, mid, no)
            self.label(mid)
            self.cond(e.right, yes, no)
        elif e.kind == "Binary" and e.op == "||":
            mid = self.new_labels("or")[0]
            self.cond(e.left, yes, mid)
            self.label(mid)
            self.cond(e.right, yes, no)
        else:
            self.emit("if", args=[self.expr(e)], target=yes)
            self.emit("goto", target=no)

    # возвращает операнд со значением e (константу, переменную или новую временную)
    def expr(self, e):
        if e.kind == "Int":
            return e.value
        if e.kind == "Bool":
            return bool(e.value)
        if e.kind == "Var":
            return self.names[(e.name, e.decl)]
        return self.expr_to(e, None)

    # вычисляет e в dst (если dst None — в новую временную)
    def expr_to(self, e, dst):
        if e.kind in ("Int", "Bool", "Var"):
            value = self.expr(e)
            if dst is None:
                dst = self.new_temp(e.type)
            self.emit("copy", dst=dst, args=[value])
            return dst
        if e.kind == "Binary" and e.op in ("&&", "||"):
            return self.short_circuit(e, dst)
        if dst is None:
            dst = self.new_temp(e.type)
        if e.kind == "Binary":
            a = self.expr(e.left)
            b = self.expr(e.right)
            self.emit("binop", dst=dst, sym=e.op, args=[a, b])
        elif e.kind == "Unary":
            self.emit("unop", dst=dst, sym=e.op, args=[self.expr(e.operand)])
        elif e.kind == "Index":
            a = self.expr(e.array)
            i = self.expr(e.index)
            self.emit("load", dst=dst, args=[a, i])
        elif e.kind == "Update":
            a = self.expr(e.array)
            i = self.expr(e.index)
            v = self.expr(e.value)
            self.emit("update", dst=dst, args=[a, i, v])
        elif e.kind == "Length":
            self.emit("length", dst=dst, args=[self.expr(e.array)])
        elif e.kind == "Call":
            args = [self.expr(a) for a in e.args]
            self.emit("call", func=e.name, args=args, dsts=[dst])
        else:
            raise ValueError("неизвестное выражение " + e.kind)
        return dst

    # значение a && b / a || b:  t := a; если нужно, t := b
    def short_circuit(self, e, dst):
        t = self.new_temp("bool")
        rhs, end = self.new_labels("rhs", "end")
        self.expr_to(e.left, t)
        if e.op == "&&":
            self.emit("if", args=[t], target=rhs)
            self.emit("goto", target=end)
        else:
            self.emit("if", args=[t], target=end)
        self.label(rhs)
        self.expr_to(e.right, t)
        self.label(end)
        if dst is None:
            return t
        self.emit("copy", dst=dst, args=[t])
        return dst


def generate(source):
    ast, diags, _ = check(source)
    if diags:
        raise CompileError(diags)
    return [Generator(f).run() for f in ast.functions]
