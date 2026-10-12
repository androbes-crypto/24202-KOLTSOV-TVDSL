import csv
import json
import os
from dataclasses import dataclass

from .dfa import DFA, NON_ASCII, char_classes, hopcroft, subset_construction
from .nfa import NFA, TokenRule, build_nfa, load_spec
from .regex import describe_chars


@dataclass
class Build:
    rules: list[TokenRule]
    nfa: NFA
    nfa_sizes: dict
    classes: list[frozenset]
    char_to_class: list[int]
    dfa: DFA
    min_dfa: DFA
    uncovered: frozenset


def build(spec_path: str) -> Build:
    rules = load_spec(spec_path)
    nfa, sizes = build_nfa(rules)
    classes = char_classes(nfa)
    c2c = [0] * 128
    for i, c in enumerate(classes):
        for ch in c:
            c2c[ch] = i
    dfa = subset_construction(nfa, classes)
    mdfa = hopcroft(dfa)
    uncovered = frozenset(c for c in range(128)
                          if mdfa.delta[mdfa.start][c2c[c]] == mdfa.trap)
    return Build(rules, nfa, sizes, classes, c2c, dfa, mdfa, uncovered)


def class_names(b: Build) -> list[str]:
    names = []
    for c in b.classes:
        tag = "UNCOVERED:" if c <= b.uncovered else ""
        names.append(tag + describe_chars(c))
    return names + [NON_ASCII]


def _label(b: Build, lab):
    return None if lab is None else b.rules[lab].name


def stats(b: Build) -> dict:
    m = b.min_dfa
    return {
        "tokens": len(b.rules),
        "nfa_states": b.nfa.size,
        "nfa_states_per_token": b.nfa_sizes,
        "symbol_classes": len(b.classes) + 1,
        "dfa_states_before_min": b.dfa.n,
        "dfa_states_after_min": m.n,
        "dfa_accepting_before_min": sum(l is not None for l in b.dfa.label),
        "dfa_accepting_after_min": sum(l is not None for l in m.label),
        "trap_state": m.trap,
        "uncovered_ascii": describe_chars(b.uncovered),
        "uncovered_ascii_count": len(b.uncovered),
    }


def to_json(b: Build) -> dict:
    m = b.min_dfa
    names = class_names(b)
    return {
        "format": "funny-dfa/1",
        "alphabet": "ASCII 0..127; code >= 128 -> class NON_ASCII -> trap",
        "tokens": [{"name": r.name, "kind": r.kind, "regex": r.regex, "priority": r.priority}
                   for r in b.rules],
        "classes": {
            "count": len(names),
            "names": names,
            "char_to_class": b.char_to_class,
            "non_ascii_class": len(names) - 1,
        },
        "start": m.start,
        "trap": m.trap,
        "states": [{"id": s, "accept": _label(b, m.label[s]),
                    "kind": None if m.label[s] is None else b.rules[m.label[s]].kind,
                    "trap": s == m.trap}
                   for s in range(m.n)],
        "transitions": m.delta,
    }


def compact_json(obj, indent=0) -> str:
    pad, pad1 = " " * indent, " " * (indent + 1)
    one = json.dumps(obj, ensure_ascii=False)
    if not isinstance(obj, (dict, list)) or len(one) <= 100 or (
            isinstance(obj, list) and all(isinstance(x, (int, float)) for x in obj)):
        return one
    if isinstance(obj, list):
        return "[\n" + ",\n".join(pad1 + compact_json(x, indent + 1) for x in obj) + "\n" + pad + "]"
    return "{\n" + ",\n".join(f"{pad1}{json.dumps(k)}: {compact_json(v, indent + 1)}"
                               for k, v in obj.items()) + "\n" + pad + "}"


def write_csv(b: Build, path: str):
    m = b.min_dfa
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["state", "accept", "kind"] + class_names(b))
        for s in range(m.n):
            lab = m.label[s]
            acc = "TRAP" if s == m.trap else (_label(b, lab) or "")
            kind = "" if lab is None else b.rules[lab].kind
            w.writerow([s, acc, kind] + m.delta[s])


def write_dot(b: Build, path: str):
    m = b.min_dfa
    with open(path, "w", encoding="utf-8") as f:
        f.write("digraph FunnyDFA {\n  rankdir=LR;\n  node [shape=circle];\n")
        f.write('  __start [shape=point];\n  __start -> 0;\n')
        for s in range(m.n):
            if s == m.trap:
                continue
            lab = _label(b, m.label[s])
            shape = "doublecircle" if lab else "circle"
            text = f"{s}\\n{lab}" if lab else str(s)
            f.write(f'  {s} [shape={shape}, label="{text}"];\n')
        for s in range(m.n):
            if s == m.trap:
                continue
            by_target = {}
            for a, t in enumerate(m.delta[s][:-1]):
                if t != m.trap:
                    by_target.setdefault(t, set()).update(b.classes[a])
            for t, chars in by_target.items():
                lbl = describe_chars(chars).replace("\\", "\\\\").replace('"', '\\"')
                f.write(f'  {s} -> {t} [label="{lbl}"];\n')
        f.write("}\n")


def write_all(b: Build, out_dir: str) -> dict:
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, "dfa.json"), "w", encoding="utf-8") as f:
        f.write(compact_json(to_json(b)))
    write_csv(b, os.path.join(out_dir, "dfa_transitions.csv"))
    write_dot(b, os.path.join(out_dir, "dfa.dot"))
    st = stats(b)
    with open(os.path.join(out_dir, "stats.json"), "w", encoding="utf-8") as f:
        json.dump(st, f, indent=2)
    return st
