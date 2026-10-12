import argparse
import glob
import json
import os
import random
import re
import sys

from .build import build, write_all
from .dfa import equivalent, run
from .lexer import DFALexer
from .testing import CaseError, run_file, show as _show

DEFAULT_SPEC = "tokens.spec"
DEFAULT_OUT = "build"


def cmd_build(args) -> int:
    b = build(args.spec)
    st = write_all(b, args.out)
    print(f"[build] spec: {args.spec}  ->  {args.out}/")
    print(f"  tokens:                 {st['tokens']}")
    print(f"  NFA states (Thompson):  {st['nfa_states']}")
    print(f"  symbol classes:         {st['symbol_classes']} (incl. NON_ASCII)")
    print(f"  DFA states (subset):    {st['dfa_states_before_min']}  (incl. trap; accepting: {st['dfa_accepting_before_min']})")
    print(f"  DFA states (Hopcroft):  {st['dfa_states_after_min']}  (incl. trap; accepting: {st['dfa_accepting_after_min']})")
    print(f"  trap state:             {st['trap_state']}")
    print(f"  ASCII -> trap from start ({st['uncovered_ascii_count']}):  {st['uncovered_ascii']}")
    print("  written: dfa.json, dfa_transitions.csv, dfa.dot, stats.json")
    return 0


def cmd_test(args) -> int:
    lexer = DFALexer.from_file(os.path.join(args.out, "dfa.json"))
    lines, total, failed = [], 0, 0
    for path in args.cases or sorted(glob.glob("tests/*.json")):
        for r in run_file(path, lexer):
            total += 1
            failed += 0 if r.ok else 1
            mark = "PASS" if r.ok else "FAIL"
            line = f"{mark}  {os.path.basename(path):<17} [{r.kind:5}] {r.name}"
            if r.detail:
                line += "\n        " + r.detail
            lines.append(line)
    summary = f"{total - failed}/{total} passed, {failed} failed"
    os.makedirs(args.out, exist_ok=True)
    with open(os.path.join(args.out, "test_results.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines + ["", summary]) + "\n")
    shown = lines if args.verbose else [l for l in lines if l.startswith("FAIL")]
    print("\n".join(shown + [summary]))
    if not args.verbose:
        print(f"(полный список: {args.out}/test_results.txt или test -v)")
    return 1 if failed else 0



def cmd_lex(args) -> int:
    lexer = DFALexer.from_file(os.path.join(args.out, "dfa.json"))
    if args.file == "-":
        text = sys.stdin.buffer.read().decode("utf-8")
    else:
        with open(args.file, encoding="utf-8", newline="") as f:
            text = f.read()
    errors = 0
    for t in lexer.tokenize(text, keep_skip=args.keep_skip):
        extra = f"  ({t.error})" if t.error else ""
        errors += t.type == "ERROR"
        print(f"{t.offset:6}  {t.type:<13} {_show(t.lexeme)}{extra}")
    return 1 if errors else 0


def main(argv=None) -> int:
    try:
        return _main(argv)
    except CaseError as e:
        print(f"ошибка в файле тестов: {e}", file=sys.stderr)
        return 2


def _main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="python -m funnylex",
                                description="HW1: regex -> NFA -> DFA -> min DFA for Funny")
    p.add_argument("--spec", default=DEFAULT_SPEC, help="token spec file")
    p.add_argument("--out", default=DEFAULT_OUT, help="output directory")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("build", help="build automata and export tables")
    t = sub.add_parser("test", help="run test cases against build/dfa.json")
    t.add_argument("cases", nargs="*")
    t.add_argument("-v", "--verbose", action="store_true")
    lx = sub.add_parser("lex", help="tokenize a file ('-' = stdin)")
    lx.add_argument("file")
    lx.add_argument("--keep-skip", action="store_true")
    a = sub.add_parser("all", help="build + test")
    a.add_argument("--samples", type=int, default=20000)
    a.add_argument("--seed", type=int, default=2026)
    a.add_argument("--programs", type=int, default=3000)
    args = p.parse_args(argv)

    if args.cmd == "all":
        rc = cmd_build(args)
        print()
        args.cases, args.verbose = [], False
        rc |= cmd_test(args)
        return rc
    return {"build": cmd_build, "test": cmd_test,
            "lex": cmd_lex}[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
