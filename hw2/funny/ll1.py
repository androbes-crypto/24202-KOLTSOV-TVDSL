import re

from .lexer import ROOT, token_names

EPS = "ε"
RESOLVED = {("else_part", "'else'"): "висячий else: выбираем 'else' (else относится к ближайшему if)"}


def load_bnf(path=ROOT / "grammar.txt") -> tuple[dict, str]:
    text = open(path, encoding="utf-8").read()
    body = text.split("== BNF ==", 1)[1].split("== END ==", 1)[0]
    rules, order, current = {}, [], None
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


def is_terminal(sym: str, rules: dict) -> bool:
    return sym not in rules


def first_of(seq, first, rules) -> set:
    out = set()
    for sym in seq:
        f = first[sym] if not is_terminal(sym, rules) else {sym}
        out |= f - {EPS}
        if EPS not in f:
            return out
    out.add(EPS)
    return out


def analyze(rules: dict, start: str):
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
                    add = (f - {EPS}) | (follow[a] if EPS in f else set())
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


def predict_table(rules: dict, first: dict, follow: dict) -> dict:
    table = {}
    for a, alts in rules.items():
        for alt in alts:
            f = first_of(alt, first, rules)
            for t in (f - {EPS}) | (follow[a] if EPS in f else set()):
                table.setdefault((a, t), []).append(alt)
    return table


def show_alt(alt) -> str:
    return " ".join(alt) if alt else EPS


def check_terminals(rules: dict) -> list[str]:
    names = token_names()
    known = set(names) | set(names.values())
    bad = []
    for alts in rules.values():
        for alt in alts:
            for sym in alt:
                if is_terminal(sym, rules) and sym not in known:
                    bad.append(sym)
    return sorted(set(bad))


def report(verbose: bool = False, table: bool = False) -> int:
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
        print(f"конфликт {what}: {a} по {t}" + (f" — разрешён: {note}" if note else " — НЕ РАЗРЕШЁН"))
        unresolved += note is None
    print("грамматика LL(1)" + (" (с учётом разрешённых конфликтов)" if conflicts else "")
          if not unresolved and not bad else "грамматика НЕ LL(1)")
    return 1 if unresolved or bad else 0
