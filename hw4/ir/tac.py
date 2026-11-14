# Трёхадресный код (TAC).
# Операнд — либо имя переменной (str), либо константа (int или bool).

VALUE_OPS = ("copy", "binop", "unop", "load", "update", "length")


def is_var(x):
    return isinstance(x, str)


def show(x):
    if is_var(x):
        return x
    if isinstance(x, bool):
        return "true" if x else "false"
    return str(x)


def same(a, b):
    # True == 1 в Python, поэтому сравниваем ещё и тип
    return type(a) is type(b) and a == b


class Instr:
    def __init__(self, op, dst=None, args=None, sym=None, target=None, func=None, dsts=None):
        self.op = op            # вид инструкции, см. README
        self.dst = dst          # куда пишем результат
        self.args = args or []  # операнды
        self.sym = sym          # знак операции: + - * < ...
        self.target = target    # метка (label, goto, if)
        self.func = func        # имя функции (call)
        self.dsts = dsts        # результаты вызова (call)

    def defs(self):
        if self.op in VALUE_OPS:
            return [self.dst]
        if self.op == "call":
            return list(self.dsts)
        return []

    def uses(self):
        return [a for a in self.args if is_var(a)]

    def copy(self):
        return Instr(self.op, self.dst, list(self.args), self.sym, self.target, self.func,
                     list(self.dsts) if self.dsts is not None else None)

    def __str__(self):
        a = [show(x) for x in self.args]
        if self.op == "label":
            return self.target + ":"
        if self.op == "copy":
            return f"{self.dst} := {a[0]}"
        if self.op == "binop":
            return f"{self.dst} := {a[0]} {self.sym} {a[1]}"
        if self.op == "unop":
            return f"{self.dst} := {self.sym}{a[0]}"
        if self.op == "load":
            return f"{self.dst} := load {a[0]}[{a[1]}]"
        if self.op == "update":
            return f"{self.dst} := update({a[0]}, {a[1]}, {a[2]})"
        if self.op == "length":
            return f"{self.dst} := length({a[0]})"
        if self.op == "call":
            text = f"call {self.func}({', '.join(a)})"
            if self.dsts:
                text = ", ".join(self.dsts) + " := " + text
            return text
        if self.op == "if":
            return f"if {a[0]} goto {self.target}"
        if self.op == "goto":
            return f"goto {self.target}"
        if self.op == "return":
            return ("return " + ", ".join(a)).strip()
        if self.op == "assert":
            return f"assert {a[0]}"
        raise ValueError(self.op)

    def to_json(self):
        res = {"op": self.op}
        if self.dst is not None:
            res["dst"] = self.dst
        if self.dsts is not None:
            res["dsts"] = self.dsts
        if self.sym is not None:
            res["sym"] = self.sym
        if self.func is not None:
            res["func"] = self.func
        if self.op not in ("label", "goto"):
            res["args"] = [operand_json(x) for x in self.args]
        if self.target is not None:
            res["target"] = self.target
        return res


def operand_json(x):
    if is_var(x):
        return {"var": x}
    if isinstance(x, bool):
        return {"bool": x}
    return {"int": x}


class Function:
    def __init__(self, name, params, results, types, temps):
        self.name = name
        self.params = params    # [(имя, тип)]
        self.results = results  # [(имя, тип)]
        self.types = types      # имя -> тип для всех переменных и временных
        self.temps = temps      # множество имён временных
        self.body = []          # список Instr

    def clone(self):
        f = Function(self.name, list(self.params), list(self.results), dict(self.types), set(self.temps))
        f.body = [i.copy() for i in self.body]
        return f

    def text(self):
        params = ", ".join(f"{n}: {t}" for n, t in self.params)
        results = ", ".join(f"{n}: {t}" for n, t in self.results)
        lines = [f"function {self.name}({params}) returns ({results})"]
        for ins in self.body:
            if ins.op == "label":
                lines.append(str(ins))
            else:
                lines.append("    " + str(ins))
        return "\n".join(lines) + "\n"

    def to_json(self):
        return {
            "name": self.name,
            "params": [{"name": n, "type": t} for n, t in self.params],
            "results": [{"name": n, "type": t} for n, t in self.results],
            "vars": {n: {"type": t, "temp": n in self.temps} for n, t in self.types.items()},
            "body": [i.to_json() for i in self.body],
        }

    def instr_count(self):
        return sum(1 for i in self.body if i.op != "label")

    def temp_count(self):
        names = set()
        for i in self.body:
            names.update(i.defs())
            names.update(i.uses())
        return len(names & self.temps)
