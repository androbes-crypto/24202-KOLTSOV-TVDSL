# Оптимизации TAC. Каждый проход меняет функцию и возвращает число сделанных замен.
#
#   const    распространение констант и копий внутри блока, свёртка констант
#   alg      алгебраические упрощения
#   cse      локальное исключение общих подвыражений
#   unreach  удаление недостижимых блоков и лишних переходов
#   dce      удаление мёртвого кода (по живым переменным)

from .cfg import build_cfg, live_after, liveness, reachable
from .interp import RunError, calc_binop, calc_unop
from .tac import Instr, is_var, same

ALL_PASSES = ["const", "alg", "cse", "unreach", "dce"]


def is_num(x, value):
    return type(x) is int and x == value


def ends_block(ins):
    return ins.op in ("goto", "if", "return")


# ---------- const ----------

def const_prop(f):
    count = 0
    known = {}  # переменная -> константа или другая переменная с тем же значением
    new_body = []
    for ins in f.body:
        if ins.op == "label":
            known = {}
            new_body.append(ins)
            continue

        # подставляем известные значения в операнды
        for k, a in enumerate(ins.args):
            if is_var(a) and a in known:
                ins.args[k] = known[a]
                count += 1

        # сворачиваем, если все операнды константы
        ins, folded = fold(ins)
        count += folded
        if ins is None:
            continue
        new_body.append(ins)

        # переменная переопределена: забываем всё, что с ней связано
        for d in ins.defs():
            known.pop(d, None)
            for k in list(known):
                if same(known[k], d):
                    del known[k]
        if ins.op == "copy" and not same(ins.args[0], ins.dst):
            known[ins.dst] = ins.args[0]
        if ends_block(ins):
            known = {}
    f.body = new_body
    return count


def fold(ins):
    consts = all(not is_var(a) for a in ins.args)
    if ins.op in ("binop", "unop") and consts:
        try:
            if ins.op == "binop":
                value = calc_binop(ins.sym, ins.args[0], ins.args[1])
            else:
                value = calc_unop(ins.sym, ins.args[0])
        except RunError:
            return ins, 0  # деление на ноль оставляем: ошибка должна случиться при выполнении
        return Instr("copy", dst=ins.dst, args=[value]), 1
    if ins.op == "if" and consts:
        if ins.args[0]:
            return Instr("goto", target=ins.target), 1
        return None, 1  # if false goto L — просто убираем
    return ins, 0


# ---------- alg ----------

def simplify(ins):
    if ins.op != "binop":
        return None
    a, b = ins.args
    s = ins.sym

    def copy(x):
        return Instr("copy", dst=ins.dst, args=[x])

    def neg(x):
        return Instr("unop", dst=ins.dst, sym="-", args=[x])

    if s == "+" and is_num(b, 0):
        return copy(a)
    if s == "+" and is_num(a, 0):
        return copy(b)
    if s == "-" and is_num(b, 0):
        return copy(a)
    if s == "-" and is_num(a, 0):
        return neg(b)
    if s == "-" and is_var(a) and a == b:
        return copy(0)
    if s == "*" and is_num(b, 1):
        return copy(a)
    if s == "*" and is_num(a, 1):
        return copy(b)
    if s == "*" and (is_num(a, 0) or is_num(b, 0)):
        return copy(0)
    if s == "/" and is_num(b, 1):
        return copy(a)
    if s == "/" and is_num(b, -1):
        return neg(a)
    # x / x не заменяем на 1: при x == 0 должно быть деление на ноль
    if s == "%" and (is_num(b, 1) or is_num(b, -1)):
        return copy(0)
    if is_var(a) and a == b:
        if s in ("==", "<=", ">="):
            return copy(True)
        if s in ("!=", "<", ">"):
            return copy(False)
    return None


def algebraic(f):
    count = 0
    for k, ins in enumerate(f.body):
        new = simplify(ins)
        if new is not None:
            f.body[k] = new
            count += 1
    return count


# ---------- cse ----------

def operand_key(x):
    if is_var(x):
        return "v:" + x
    return "c:" + str(x)  # str(True) = "True", str(1) = "1" — не путаются


def expr_key(ins):
    # call не трогаем: про функцию неизвестно, что она чистая
    if ins.op not in ("binop", "unop", "load", "update", "length"):
        return None
    ops = [operand_key(a) for a in ins.args]
    if ins.op == "binop" and ins.sym in ("+", "*", "==", "!="):
        ops.sort()
    return (ins.op, ins.sym) + tuple(ops)


def cse(f):
    count = 0
    available = {}  # выражение -> переменная, в которой уже лежит его значение
    for k, ins in enumerate(f.body):
        if ins.op == "label":
            available = {}
            continue
        key = expr_key(ins)
        if key is not None and key in available:
            ins = Instr("copy", dst=ins.dst, args=[available[key]])
            f.body[k] = ins
            count += 1
            key = None
        for d in ins.defs():
            for old in list(available):
                if available[old] == d or "v:" + d in old:
                    del available[old]
        if key is not None and "v:" + ins.dst not in key:
            available[key] = ins.dst
        if ends_block(ins):
            available = {}
    return count


# ---------- unreach ----------

def remove_unreachable(f):
    count = 0
    blocks = build_cfg(f.body)
    reach = reachable(blocks)
    body = []
    for b in blocks:
        if b.name in reach:
            body.extend(b.instrs)
        else:
            count += 1

    # убираем goto на следующую метку и if, у которого обе ветки ведут туда же
    cleaned = []
    for k, ins in enumerate(body):
        next_labels = set()
        j = k + 1
        while j < len(body) and body[j].op == "label":
            next_labels.add(body[j].target)
            j += 1
        if ins.op in ("goto", "if") and ins.target in next_labels:
            count += 1
            continue
        if ins.op == "if" and k + 1 < len(body) and body[k + 1].op == "goto" \
                and body[k + 1].target == ins.target:
            count += 1
            continue
        cleaned.append(ins)

    # метки, на которые никто не переходит, тоже не нужны
    used = {ins.target for ins in cleaned if ins.op in ("goto", "if")}
    f.body = []
    for ins in cleaned:
        if ins.op == "label" and ins.target not in used:
            count += 1
        else:
            f.body.append(ins)
    return count


# ---------- dce ----------

def can_remove(ins):
    # x := e можно удалить, если x мёртвая, а e не может упасть (лекция 6)
    if ins.op in ("copy", "unop", "length"):
        return True
    if ins.op == "binop":
        if ins.sym in ("/", "%"):
            divisor = ins.args[1]
            return type(divisor) is int and divisor != 0
        return True  # + - * по модулю 2^32 никогда не падают
    return False  # load/update — выход за границы, call — что угодно


def dce(f):
    count = 0
    blocks = build_cfg(f.body)
    _, live_out = liveness(blocks)
    f.body = []
    for b in blocks:
        after = live_after(b, live_out[b.name])
        for ins, live in zip(b.instrs, after):
            if ins.op == "copy" and same(ins.args[0], ins.dst):
                count += 1
                continue
            if ins.dst is not None and ins.dst not in live and can_remove(ins):
                count += 1
                continue
            f.body.append(ins)
    return count


PASSES = {"const": const_prop, "alg": algebraic, "cse": cse, "unreach": remove_unreachable, "dce": dce}


def parse_passes(text):
    text = text.strip()
    if text in ("", "none"):
        return []
    if text == "all":
        return list(ALL_PASSES)
    names = [x.strip() for x in text.split(",") if x.strip()]
    for n in names:
        if n not in PASSES:
            raise ValueError(f"неизвестная оптимизация '{n}' (есть: {', '.join(ALL_PASSES)}, all, none)")
    return [n for n in ALL_PASSES if n in names]


def optimize(f, passes):
    # гоняем включённые проходы по кругу, пока что-то меняется
    f = f.clone()
    stats = {p: 0 for p in passes}
    for _ in range(50):
        changed = 0
        for p in passes:
            n = PASSES[p](f)
            stats[p] += n
            changed += n
        if changed == 0:
            break
    return f, stats
