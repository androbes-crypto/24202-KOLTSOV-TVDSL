import re

from .lexer import ROOT, TOKEN_NAMES

EPS = "ε"
RESOLVED = {("else_part", "'else'"): "висячий else: выбираем 'else' (else относится к ближайшему if)"}


# читает BNF между строками '== BNF ==' и '== END ==' в grammar.txt
def load_bnf(path=ROOT / "grammar.txt"):
    text = open(path, encoding="utf-8").read()
    body = text.split("== BNF ==", 1)[1].split("== END ==", 1)[0]
    rules = {}
    order = []
    current = None
    for raw in body.splitlines():
        line = raw.strip()
        if not line:
            continue
        m = re.match(r"([a-z_]+)\s*->\s*(.*)$", line)
        if m:
            current = m.group(1)
            order.append(current)
            rules[current] = []
            rest = m.group(2)
        elif line.startswith("|") and current:
            rest = line[1:]
        else:
            raise ValueError(f"не понимаю строку грамматики: {line}")
        for alt in rest.split(" | "):
            syms = re.findall(r"'[^']*'|\S+", alt.strip())
            rules[current].append([] if syms == [EPS] else syms)
    return rules, order[0]


def is_terminal(sym, rules):
    return sym not in rules


# FIRST цепочки символов
def first_of(seq, first, rules):
    out = set()
    for sym in seq:
        if is_terminal(sym, rules):
            f = {sym}
        else:
            f = first[sym]
        out |= f - {EPS}
        if EPS not in f:
            return out
    out.add(EPS)
    return out


# FIRST и FOLLOW итерациями до неподвижной точки, затем поиск конфликтов LL(1)
def analyze(rules, start):
    first = {a: set() for a in rules}
    changed = True
    while changed:
        changed = False
        for a, alts in rules.items():
            for alt in alts:
                f = first_of(alt, first, rules)
                if not f <= first[a]:
                    first[a] |= f
                    changed = True
    follow = {a: set() for a in rules}
    changed = True
    while changed:
        changed = False
        for a, alts in rules.items():
            for alt in alts:
                for i, sym in enumerate(alt):
                    if is_terminal(sym, rules):
                        continue
                    f = first_of(alt[i + 1:], first, rules)
                    add = f - {EPS}
                    if EPS in f:
                        add |= follow[a]
                    if not add <= follow[sym]:
                        follow[sym] |= add
                        changed = True
    conflicts = []
    for a, alts in rules.items():
        firsts = [first_of(alt, first, rules) for alt in alts]
        for i in range(len(alts)):
            for j in range(i + 1, len(alts)):
                for t in sorted((firsts[i] & firsts[j]) - {EPS}):
                    conflicts.append((a, t, "FIRST/FIRST"))
            if EPS in firsts[i]:
                for j in range(len(alts)):
                    if j != i:
                        for t in sorted(firsts[j] & follow[a]):
                            conflicts.append((a, t, "FIRST/FOLLOW"))
    return first, follow, conflicts


def predict_table(rules, first, follow):
    table = {}
    for a, alts in rules.items():
        for alt in alts:
            f = first_of(alt, first, rules)
            columns = f - {EPS}
            if EPS in f:
                columns |= follow[a]
            for t in columns:
                table.setdefault((a, t), []).append(alt)
    return table


def show_alt(alt):
    if not alt:
        return EPS
    return " ".join(alt)


# все терминалы грамматики должны быть токенами из tokens.spec
def check_terminals(rules):
    known = set(TOKEN_NAMES) | set(TOKEN_NAMES.values())
    bad = []
    for alts in rules.values():
        for alt in alts:
            for sym in alt:
                if is_terminal(sym, rules) and sym not in known:
                    bad.append(sym)
    return sorted(set(bad))


def report(verbose=False, table=False):
    rules, start = load_bnf()
    first, follow, conflicts = analyze(rules, start)
    if table:
        m = predict_table(rules, first, follow)
        print("таблица предсказаний M[нетерминал, токен] -> правая часть:")
        for a in rules:
            print(f"  {a}")
            for (b, t), alts in sorted(m.items(), key=lambda kv: kv[0][1]):
                if b == a:
                    mark = "   <-- конфликт" if len(alts) > 1 else ""
                    print(f"    {t:12} -> {' | '.join(show_alt(x) for x in alts)}{mark}")
    print(f"нетерминалов: {len(rules)}, правил: {sum(len(a) for a in rules.values())}")
    bad = check_terminals(rules)
    if bad:
        print("терминалы, которых нет в tokens.spec:", " ".join(bad))
    if verbose:
        for a in rules:
            print(f"  {a:15} FIRST = {{{' '.join(sorted(first[a]))}}}")
            print(f"  {'':15} FOLLOW = {{{' '.join(sorted(follow[a]))}}}")
    unresolved = 0
    for a, t, what in conflicts:
        note = RESOLVED.get((a, t))
        if note:
            print(f"конфликт {what}: {a} по {t} — разрешён: {note}")
        else:
            print(f"конфликт {what}: {a} по {t} — НЕ РАЗРЕШЁН")
            unresolved += 1
    if unresolved or bad:
        print("грамматика НЕ LL(1)")
        return 1
    if conflicts:
        print("грамматика LL(1) (с учётом разрешённых конфликтов)")
    else:
        print("грамматика LL(1)")
    return 0
