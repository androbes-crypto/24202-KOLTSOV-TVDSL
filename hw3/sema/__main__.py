import argparse
import sys

from .checker import check
from funny import dumps, to_text


def read(path):
    if path == "-":
        return sys.stdin.read()
    with open(path, encoding="utf-8", newline="") as f:
        return f.read()


def cmd_check(args):
    ast, diags, summary = check(read(args.file))
    for d in diags:
        print(f"{args.file}:{d.line}:{d.col}: ошибка: {d.message}", file=sys.stderr)
    if summary is not None and (not diags or args.partial):
        if args.symbols:
            print("\n".join(summary))
        elif args.json:
            print(dumps(ast))
        else:
            print(to_text(ast), end="")
    if diags:
        print(f"ошибок: {len(diags)}", file=sys.stderr)
    return 1 if diags else 0


def cmd_test(args):
    from .testing import run
    results = run(update=args.update)
    failed = 0
    for r in results:
        if not r.ok:
            failed += 1
        if args.verbose or not r.ok:
            print(f"{'PASS' if r.ok else 'FAIL'}  [{r.group:3}] {r.name}")
            if r.detail:
                print(f"        {r.detail}")
    print(f"{len(results) - failed}/{len(results)} passed, {failed} failed"
          + (" (эталоны перезаписаны)" if args.update else ""))
    return 1 if failed else 0


def main(argv=None):
    p = argparse.ArgumentParser(prog="python3 -m sema", description="HW3: семантические проверки и типы Funny")
    sub = p.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("check", help="проверить программу и вывести аннотированный AST")
    c.add_argument("file", help="файл с программой ('-' = stdin)")
    c.add_argument("--json", action="store_true", help="аннотированный AST в JSON")
    c.add_argument("--symbols", action="store_true", help="только сигнатуры функций и типы локальных переменных")
    c.add_argument("--partial", action="store_true", help="выводить AST и при семантических ошибках")
    t = sub.add_parser("test", help="прогнать tests/positive.txt и tests/negative.txt")
    t.add_argument("-v", "--verbose", action="store_true")
    t.add_argument("--update", action="store_true", help="перезаписать ожидаемые результаты")
    args = p.parse_args(argv)
    if args.cmd == "check":
        return cmd_check(args)
    return cmd_test(args)


if __name__ == "__main__":
    sys.exit(main())
