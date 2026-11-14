# Интерпретатор TAC: нужен, чтобы сравнить работу программы до и после оптимизаций.
# int — 32 бита, переполнение по модулю 2^32 (funny.ru.md); деление как в JVM (idiv/irem).

import json

from .tac import is_var

DIV_BY_ZERO = "деление на ноль"
OUT_OF_BOUNDS = "выход за границы массива"
ASSERT_FAILED = "нарушение assert"
UNINIT = "чтение неинициализированной переменной"
TOO_LONG = "превышен лимит шагов"

STEP_LIMIT = 200000


class RunError(Exception):
    def __init__(self, kind):
        super().__init__(kind)
        self.kind = kind


def wrap(v):
    return (v + 2 ** 31) % 2 ** 32 - 2 ** 31


def divide(a, b):
    if b == 0:
        raise RunError(DIV_BY_ZERO)
    q = abs(a) // abs(b)
    if (a < 0) != (b < 0):
        q = -q
    return wrap(q)


def calc_binop(sym, a, b):
    if sym == "+":
        return wrap(a + b)
    if sym == "-":
        return wrap(a - b)
    if sym == "*":
        return wrap(a * b)
    if sym == "/":
        return divide(a, b)
    if sym == "%":
        return wrap(a - b * divide(a, b))
    if sym == "<":
        return a < b
    if sym == "<=":
        return a <= b
    if sym == ">":
        return a > b
    if sym == ">=":
        return a >= b
    if sym == "==":
        return a == b
    if sym == "!=":
        return a != b
    raise ValueError(sym)


def calc_unop(sym, a):
    if sym == "-":
        return wrap(-a)
    return not a


def check_index(arr, i):
    if i < 0 or i >= len(arr):
        raise RunError(OUT_OF_BOUNDS)


class Interpreter:
    def __init__(self, funcs):
        self.funcs = {f.name: f for f in funcs}
        self.steps = 0

    def call(self, name, args):
        f = self.funcs[name]
        labels = {}
        for k, ins in enumerate(f.body):
            if ins.op == "label":
                labels[ins.target] = k
        env = {}
        for (p, _), value in zip(f.params, args):
            env[p] = value

        def val(x):
            if not is_var(x):
                return x
            if x not in env:
                raise RunError(UNINIT)
            return env[x]

        pc = 0
        while pc < len(f.body):
            self.steps += 1
            if self.steps > STEP_LIMIT:
                raise RunError(TOO_LONG)
            ins = f.body[pc]
            pc += 1
            a = [val(x) for x in ins.args] if ins.op != "label" else []
            if ins.op == "copy":
                env[ins.dst] = a[0]
            elif ins.op == "binop":
                env[ins.dst] = calc_binop(ins.sym, a[0], a[1])
            elif ins.op == "unop":
                env[ins.dst] = calc_unop(ins.sym, a[0])
            elif ins.op == "load":
                check_index(a[0], a[1])
                env[ins.dst] = a[0][a[1]]
            elif ins.op == "update":
                # массивы неизменяемые: update возвращает новый кортеж
                check_index(a[0], a[1])
                env[ins.dst] = a[0][:a[1]] + (a[2],) + a[0][a[1] + 1:]
            elif ins.op == "length":
                env[ins.dst] = len(a[0])
            elif ins.op == "call":
                res = self.call(ins.func, a)
                for d, v in zip(ins.dsts, res):
                    env[d] = v
            elif ins.op == "if":
                if a[0]:
                    pc = labels[ins.target]
            elif ins.op == "goto":
                pc = labels[ins.target]
            elif ins.op == "assert":
                if not a[0]:
                    raise RunError(ASSERT_FAILED)
            elif ins.op == "return":
                return tuple(a)
        raise RuntimeError("функция закончилась без return")


def run(funcs, name, args):
    # результат: ("ok", кортеж результатов) или ("error", описание ошибки)
    try:
        return "ok", Interpreter(funcs).call(name, args)
    except RunError as e:
        return "error", e.kind
    except RecursionError:
        return "error", TOO_LONG


def value_text(v):
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, tuple):
        return "[" + ", ".join(value_text(x) for x in v) + "]"
    return str(v)


def outcome_text(outcome):
    if outcome[0] == "error":
        return "ошибка: " + outcome[1]
    return "(" + ", ".join(value_text(x) for x in outcome[1]) + ")"


def parse_call(text):
    # "f(1, true, [1, 2])" -> ("f", [1, True, (1, 2)])
    text = text.strip()
    if "(" not in text or not text.endswith(")"):
        raise ValueError(f"ожидался вызов вида f(1, [2, 3]), а получено {text!r}")
    name, rest = text.split("(", 1)
    try:
        values = json.loads("[" + rest[:-1] + "]")
    except json.JSONDecodeError:
        raise ValueError(f"не удалось разобрать аргументы {rest[:-1]!r}")
    return name.strip(), [to_tuples(v) for v in values]


def to_tuples(v):
    if isinstance(v, list):
        return tuple(to_tuples(x) for x in v)
    return v
