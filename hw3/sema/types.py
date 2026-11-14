# Типы Funny и унификация.
#   int, bool, массивы T[], типы функций (только у функций),
#   переменная типа (для вывода типов локальных) и тип-ошибка (чтобы не плодить сообщения).


class Type:
    pass


class Prim(Type):
    def __init__(self, name):
        self.name = name

    def __repr__(self):
        return self.name


INT = Prim("int")
BOOL = Prim("bool")


class ErrorType(Type):
    def __repr__(self):
        return "<ошибка>"


ERROR = ErrorType()


class Array(Type):
    def __init__(self, elem):
        self.elem = elem


class Func(Type):
    def __init__(self, params, results):
        self.params = params
        self.results = results


class Var(Type):
    # переменная типа: ref становится известным типом после первого присваивания
    def __init__(self):
        self.ref = None


def prune(t):
    # идём по ссылкам переменных типа до настоящего типа
    while isinstance(t, Var) and t.ref is not None:
        t = t.ref
    return t


def is_complete(t):
    t = prune(t)
    if isinstance(t, Var):
        return False
    if isinstance(t, Array):
        return is_complete(t.elem)
    return True


def show(t):
    t = prune(t)
    if isinstance(t, Array):
        return show(t.elem) + "[]"
    if isinstance(t, Var):
        return "?"
    if isinstance(t, Func):
        params = ", ".join(show(p) for p in t.params)
        results = ", ".join(show(r) for r in t.results)
        return f"({params}) -> ({results})"
    return repr(t)


def from_annotation(text):
    # "int[][]" -> Array(Array(INT))
    base = text.rstrip("[]")
    if base == "int":
        t = INT
    else:
        t = BOOL
    dims = (len(text) - len(base)) // 2
    for _ in range(dims):
        t = Array(t)
    return t


def unify(a, b):
    a = prune(a)
    b = prune(b)
    if a is ERROR or b is ERROR or a is b:
        return True
    if isinstance(a, Var):
        a.ref = b
        return True
    if isinstance(b, Var):
        b.ref = a
        return True
    if isinstance(a, Array) and isinstance(b, Array):
        return unify(a.elem, b.elem)
    return False


def contains_error(t):
    t = prune(t)
    if t is ERROR:
        return True
    if isinstance(t, Array):
        return contains_error(t.elem)
    return False
