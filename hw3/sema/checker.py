import os
import sys
from pathlib import Path

from .types import BOOL, ERROR, INT, Array, Func, Var, contains_error, from_annotation, is_complete, prune, show, unify

ROOT = Path(__file__).resolve().parent.parent
HW2 = Path(os.environ.get("FUNNY_HW2", ROOT.parent / "hw2")).resolve()
if not (HW2 / "funny").is_dir():
    raise RuntimeError(f"не найден парсер HW2 в {HW2} (укажите путь в FUNNY_HW2)")
if str(HW2) not in sys.path:
    sys.path.insert(0, str(HW2))

from funny import Diagnostic, Node, parse

ARITH = {"+", "-", "*", "/", "%"}
ORDER = {"<", "<=", ">", ">="}
EQUAL = {"==", "!="}
LOGIC = {"&&", "||"}


class Symbol:
    def __init__(self, name, kind, type_, node, annotated=True):
        self.name = name
        self.kind = kind  # "param", "result" или "local"
        self.type = type_
        self.node = node
        self.line = node.line
        self.col = node.col
        self.annotated = annotated
        self.pos = f"{self.line}:{self.col}"


class FunctionInfo:
    def __init__(self, node, params, results):
        self.node = node
        self.name = node.name
        self.params = params
        self.results = results
        self.type = Func([p.type for p in params], [r.type for r in results])


# Проверка программы: сначала собираем сигнатуры всех функций, потом проверяем тела.
class Checker:
    def __init__(self):
        self.diags = []
        self.functions = {}
        self.summary = []

    def error(self, at, message):
        self.diags.append(Diagnostic(at.line, at.col, message))

    def check_program(self, program):
        infos = [self.declare_function(f) for f in program.functions]
        for info in infos:
            self.check_function(info)
        self.diags.sort(key=lambda d: (d.line, d.col))

    def declare_function(self, f):
        seen = {}

        def make(p, kind):
            if p.type is None:
                what = "параметра" if kind == "param" else "результата"
                self.error(p, f"не указан тип {what} '{p.name}': типы параметров и результатов функции "
                              f"обязательны")
                t = ERROR
            else:
                t = from_annotation(p.type)
            sym = Symbol(p.name, kind, t, p)
            if p.name in seen:
                prev = seen[p.name]
                self.error(p, f"имя '{p.name}' уже занято: {'параметр' if prev.kind == 'param' else 'результат'} "
                              f"'{p.name}' объявлен в {prev.pos}")
            else:
                seen[p.name] = sym
            return sym

        params = [make(p, "param") for p in f.params]
        results = [make(r, "result") for r in f.returns]
        info = FunctionInfo(f, params, results)
        if f.name in self.functions:
            prev = self.functions[f.name].node
            self.error(f, f"функция '{f.name}' уже объявлена в {prev.line}:{prev.col}")
        else:
            self.functions[f.name] = info
        f.fields["signature"] = show(info.type)
        return info

    def check_function(self, info):
        f = info.node
        self.info = info
        self.typed = []
        self.locals = []
        self.declaring = None
        self.phase = "body"
        scope = {}
        for sym in info.params + info.results:
            scope.setdefault(sym.name, sym)
        self.scopes = [scope]
        self.decls = {}
        if f.body is not None:
            self.collect_decls(f.body)
        self.phase = "requires"
        for e in f.requires:
            self.condition(e, "requires")
        self.phase = "ensures"
        for e in f.ensures:
            self.condition(e, "ensures")
        self.phase = "body"
        if f.body is not None:
            self.block(f.body)
        for sym in self.locals:
            if contains_error(sym.type) or is_complete(sym.type):
                continue
            self.error(sym.node, f"не удалось вывести тип переменной '{sym.name}': ей ничего не присваивается "
                                 f"(укажите тип: var {sym.name}: int;)")
            prune(sym.type).ref = ERROR
        self.annotate(info)

    # все var функции заранее: чтобы различать "до объявления" и "не видна вне блока"
    def collect_decls(self, node):
        if isinstance(node, Node):
            if node.kind == "VarDecl":
                self.decls.setdefault(node.name, []).append(node)
            for v in node.fields.values():
                self.collect_decls(v)
        elif isinstance(node, list):
            for x in node:
                self.collect_decls(x)

    # записываем типы в AST (поля type, inferred) и строки для --symbols
    def annotate(self, info):
        for node, t in self.typed:
            node.fields["type"] = show(t)
        for sym in self.locals:
            sym.node.fields["type"] = show(sym.type)
            sym.node.fields["inferred"] = not sym.annotated
        lines = [f"function {info.name}({', '.join(f'{p.name}: {show(p.type)}' for p in info.params)}) "
                 f"returns ({', '.join(f'{r.name}: {show(r.type)}' for r in info.results)})"]
        for sym in self.locals:
            lines.append(f"  local {sym.name}: {show(sym.type)} @{sym.pos}"
                         + ("" if sym.annotated else " (выведен)"))
        self.summary.extend(lines)

    def find(self, name):
        for scope in reversed(self.scopes):
            if name in scope:
                return scope[name]
        return None

    def lookup(self, name, at):
        sym = self.find(name)
        if sym is not None:
            return sym
        if self.declaring == name:
            self.error(at, f"переменная '{name}' используется в собственной инициализации")
        elif name in self.functions:
            self.error(at, f"'{name}' — функция, её нельзя использовать как переменную")
        else:
            decls = self.decls.get(name, [])
            later = [d for d in decls if (d.line, d.col) > (at.line, at.col)]
            if later:
                d = later[0]
                self.error(at, f"переменная '{name}' используется до объявления (объявлена в {d.line}:{d.col})")
            elif decls:
                d = decls[-1]
                self.error(at, f"переменная '{name}' здесь не видна: она объявлена в {d.line}:{d.col} "
                               f"во внутреннем блоке")
            else:
                self.error(at, f"неизвестное имя '{name}'")
        return None

    def read(self, name, at):
        sym = self.lookup(name, at)
        if sym is None:
            return None, ERROR
        at.fields["ref"] = sym.kind
        at.fields["decl"] = sym.pos
        if self.phase == "requires" and sym.kind == "result":
            self.error(at, f"результат '{name}' нельзя использовать в requires: он ещё не вычислен")
            return sym, ERROR
        if isinstance(prune(sym.type), Var):
            self.error(at, f"тип переменной '{name}' ещё не известен: она используется до первого "
                           f"присваивания (объявлена в {sym.pos})")
            return sym, ERROR
        return sym, sym.type

    # x = e: при выводе типа первое присваивание задаёт тип x
    def assign_to(self, sym, value_type, at):
        if sym is None:
            return
        target = prune(sym.type)
        if contains_error(value_type):
            if isinstance(target, Var):
                target.ref = ERROR
            return
        if isinstance(target, Var) and not is_complete(value_type):
            self.error(at, f"не удалось вывести тип переменной '{sym.name}': тип значения не определён")
            target.ref = ERROR
            return
        if not unify(sym.type, value_type):
            self.error(at, f"нельзя присвоить {show(value_type)} в '{sym.name}' типа {show(sym.type)}")

    def block(self, node):
        self.scopes.append({})
        for s in node.stmts:
            self.statement(s)
        self.scopes.pop()

    def scoped(self, node):
        if node is None:
            return
        if node.kind == "Block":
            self.block(node)
        else:
            self.scopes.append({})
            self.statement(node)
            self.scopes.pop()

    def statement(self, s):
        k = s.kind
        if k == "Block":
            self.block(s)
        elif k == "VarDecl":
            self.var_decl(s)
        elif k == "Assign":
            value_type = self.expr(s.value)
            if s.fields.get("sugar"):
                sym = self.find(s.target)
            else:
                sym = self.lookup(s.target, s)
            if sym is not None:
                s.fields["ref"] = sym.kind
                s.fields["decl"] = sym.pos
            self.assign_to(sym, value_type, s)
        elif k == "If":
            self.condition(s.cond, "if")
            self.scoped(s.then)
            self.scoped(s.orelse)
        elif k == "While":
            self.condition(s.cond, "while")
            for inv in s.invariants:
                self.condition(inv, "invariant")
            self.scoped(s.body)
        elif k in ("Assert", "Assume"):
            self.condition(s.cond, k.lower())
        elif k == "CallStmt":
            self.call(s.call, as_statement=True)

    def var_decl(self, s):
        name = s.name
        annotated = s.type is not None
        declared = from_annotation(s.type) if annotated else Var()
        init_type = None
        if s.init is not None:
            self.declaring = name
            init_type = self.expr(s.init)
            self.declaring = None
        current = self.scopes[-1]
        if name in current:
            self.error(s, f"переменная '{name}' уже объявлена в этом блоке ({current[name].pos})")
            sym = None
        else:
            outer = self.find(name)
            if outer is not None:
                self.error(s, f"имя '{name}' уже объявлено в {outer.pos}, перекрывать имена нельзя")
            sym = Symbol(name, "local", declared, s, annotated)
            current[name] = sym
            self.locals.append(sym)
        if s.init is not None:
            self.assign_to(sym, init_type, s.init)

    def condition(self, e, where):
        t = self.expr(e)
        if not contains_error(t) and not unify(t, BOOL):
            self.error(e, f"условие {where} должно иметь тип bool, а имеет тип {show(t)}")

    def expr(self, n):
        t = self._expr(n)
        self.typed.append((n, t))
        return t

    def need(self, t, want, at, message):
        if contains_error(t):
            return False
        if not unify(t, want):
            self.error(at, message)
            return False
        return True

    def element(self, t, at):
        p = prune(t)
        if contains_error(p):
            return ERROR
        if isinstance(p, Array):
            return p.elem
        self.error(at, f"индексировать можно только массив, а здесь значение типа {show(p)}")
        return ERROR

    def _expr(self, n):
        k = n.kind
        if k == "Int":
            return INT
        if k == "Bool":
            return BOOL
        if k == "Var":
            return self.read(n.name, n)[1]
        if k == "Unary":
            t = self.expr(n.operand)
            want = INT if n.op == "-" else BOOL
            self.need(t, want, n.operand,
                      f"оператор '{n.op}' применим только к {show(want)}, а операнд имеет тип {show(t)}")
            return want
        if k == "Binary":
            lt = self.expr(n.left)
            rt = self.expr(n.right)
            if n.op in EQUAL:
                if not contains_error(lt) and not contains_error(rt) and not unify(lt, rt):
                    self.error(n, f"нельзя сравнивать '{n.op}' значения разных типов: {show(lt)} и {show(rt)}")
                return BOOL
            want = BOOL if n.op in LOGIC else INT
            for side, t, word in ((n.left, lt, "левый"), (n.right, rt, "правый")):
                self.need(t, want, side, f"оператор '{n.op}' требует {show(want)}, а {word} операнд "
                                         f"имеет тип {show(t)}")
            return INT if n.op in ARITH else BOOL
        if k == "Index":
            ta = self.expr(n.array)
            ti = self.expr(n.index)
            self.need(ti, INT, n.index, f"индекс массива должен быть int, а имеет тип {show(ti)}")
            return self.element(ta, n.array)
        if k == "Update":
            ta = self.expr(n.array)
            ti = self.expr(n.index)
            tv = self.expr(n.value)
            self.need(ti, INT, n.index, f"индекс массива должен быть int, а имеет тип {show(ti)}")
            elem = self.element(ta, n.array)
            if not contains_error(elem) and not contains_error(tv) and not unify(elem, tv):
                self.error(n.value, f"в массив {show(ta)} нельзя записать значение типа {show(tv)}")
            return ta
        if k == "Length":
            ta = self.expr(n.array)
            p = prune(ta)
            if not contains_error(p) and not isinstance(p, Array):
                self.error(n.array, f"length применим только к массиву, а аргумент имеет тип {show(p)}")
            return INT
        if k == "Call":
            return self.call(n, as_statement=False)
        self.error(n, f"неизвестный узел выражения {k}")
        return ERROR

    def call(self, n, as_statement):
        arg_types = [self.expr(a) for a in n.args]
        info = self.functions.get(n.name)
        if info is None:
            if self.find(n.name) is not None:
                self.error(n, f"'{n.name}' — переменная, а не функция; вызывать её нельзя")
            else:
                self.error(n, f"неизвестная функция '{n.name}'")
            if as_statement:
                n.fields["type"] = show(ERROR)
            return ERROR
        n.fields["signature"] = show(info.type)
        want, got = len(info.params), len(arg_types)
        if want != got:
            self.error(n, f"функция '{n.name}': ожидалось аргументов {want}, передано {got}")
        else:
            for i, (arg, t, p) in enumerate(zip(n.args, arg_types, info.params), 1):
                if not contains_error(t) and not contains_error(p.type) and not unify(t, p.type):
                    self.error(arg, f"аргумент {i} функции '{n.name}' ('{p.name}') должен иметь тип "
                                    f"{show(p.type)}, а передан {show(t)}")
        results = info.results
        if as_statement:
            n.fields["type"] = "(" + ", ".join(show(r.type) for r in results) + ")"
            return None
        if len(results) == 1:
            return results[0].type
        if not results:
            self.error(n, f"функция '{n.name}' ничего не возвращает, её нельзя использовать в выражении")
        else:
            self.error(n, f"функция '{n.name}' возвращает {len(results)} значения, в выражении можно использовать "
                          f"только функцию с одним результатом")
        return ERROR


def check(text):
    ast, diags = parse(text)
    if diags:
        return ast, diags, None
    checker = Checker()
    checker.check_program(ast)
    return ast, checker.diags, checker.summary
