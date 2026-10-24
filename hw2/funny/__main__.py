import argparse
import sys

from .lexer import build_table, lex
from .ll1 import report
from .nodes import dumps, to_text
from .parser import parse


def read(path: str) -> str:
    if path == "-":
        return sys.stdin.buffer.read().decode("utf-8")
    with open(path, encoding="utf-8", newline="") as f:
        return f.read()


def cmd_parse(args) -> int:
    ast, diags = parse(read(args.file))
    for d in diags:
        print(f"{args.file}:{d.line}:{d.col}: ошибка: {d.message}", file=sys.stderr)
    if not diags or args.partial:
        print(dumps(ast) if args.json else to_text(ast), end="" if not args.json else "\n")
    if diags:
        print(f"ошибок: {len(diags)}", file=sys.stderr)
    return 1 if diags else 0


def cmd_tokens(args) -> int:
    tokens, diags = lex(read(args.file))
    for t in tokens:
        print(t)
    for d in diags:
        print(f"{args.file}:{d}", file=sys.stderr)
    return 1 if diags else 0


def cmd_test(args) -> int:
    from .testing import run_fuzz, run_snapshots
    results = run_snapshots(update=args.update)
    if not args.update:
        results.append(run_fuzz(args.fuzz))
    failed = 0
    for r in results:
        failed += not r.ok
        if args.verbose or not r.ok or r.group == "fuzz":
            print(f"{'PASS' if r.ok else 'FAIL'}  [{r.group:4}] {r.name}")
            if r.detail:
                print(f"        {r.detail}")
    print(f"{len(results) - failed}/{len(results)} passed, {failed} failed"
          + (" (эталоны перезаписаны)" if args.update else ""))
    return 1 if failed else 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="python3 -m funny", description="HW2: LL(1)-парсер языка Funny")
    sub = p.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("parse", help="разобрать программу и вывести AST")
    a.add_argument("file", help="файл с программой ('-' = stdin)")
    a.add_argument("--json", action="store_true", help="AST в JSON (по умолчанию — текстовое дерево)")
    a.add_argument("--partial", action="store_true", help="выводить AST и при ошибках")
    t = sub.add_parser("tokens", help="показать токены с позициями")
    t.add_argument("file")
    s = sub.add_parser("test", help="snapshot-тесты и проверка на зацикливание")
    s.add_argument("-v", "--verbose", action="store_true")
    s.add_argument("--update", action="store_true", help="перезаписать эталоны")
    s.add_argument("--fuzz", type=int, default=2000)
    l1 = sub.add_parser("ll1", help="проверить, что грамматика LL(1)")
    l1.add_argument("-v", "--verbose", action="store_true", help="напечатать FIRST и FOLLOW")
    l1.add_argument("--table", action="store_true", help="напечатать таблицу предсказаний LL(1)")
    sub.add_parser("build-lexer", help="пересобрать таблицу лексера из tokens.spec (через HW1)")
    args = p.parse_args(argv)
    if args.cmd == "build-lexer":
        print(f"таблица лексера: {build_table(force=True)}")
        return 0
    if args.cmd == "ll1":
        return report(args.verbose, args.table)
    return {"parse": cmd_parse, "tokens": cmd_tokens, "test": cmd_test}[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
