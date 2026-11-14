import argparse
import json
import sys
from pathlib import Path

from . import CompileError, compile_program, parse_passes
from .cfg import build_cfg, cfg_dot, cfg_json, cfg_text
from .interp import outcome_text, parse_call, run
from .regs import colors_count, graph_dot, graph_json, graph_text, greedy_coloring, interference, spilled


def read(path):
    if path == "-":
        return sys.stdin.read()
    with open(path, encoding="utf-8") as f:
        return f.read()


def load(args):
    # None, если в программе синтаксические или семантические ошибки
    passes = parse_passes(args.opt)
    try:
        return compile_program(read(args.file), passes)
    except CompileError as e:
        for d in e.diagnostics:
            print(f"{args.file}:{d.line}:{d.col}: ошибка: {d.message}", file=sys.stderr)
        print(f"ошибок: {len(e.diagnostics)}", file=sys.stderr)
        return None


def metrics(f, registers):
    color = greedy_coloring(interference(f))
    return {
        "instructions": f.instr_count(),
        "temporaries": f.temp_count(),
        "blocks": len(build_cfg(f.body)),
        "colors": colors_count(color),
        "spilled": len(spilled(color, registers)),
    }


def metrics_text(before, after, stats, registers):
    m1 = metrics(before, registers)
    m2 = metrics(after, registers)
    names = [("инструкций", "instructions"), ("временных", "temporaries"), ("блоков", "blocks"), ("цветов", "colors")]
    if registers is not None:
        names.append(("в памяти", "spilled"))
    parts = [f"{title} {m1[key]} -> {m2[key]}" for title, key in names]
    text = f"{before.name}: " + ", ".join(parts) + "\n"
    if stats:
        text += "  замен: " + ", ".join(f"{p} {n}" for p, n in stats.items()) + "\n"
    return text


def print_section(title, parts):
    print(f"== {title} ==")
    print("\n".join(parts), end="")
    print()


def cmd_build(args):
    program = load(args)
    if program is None:
        return 1

    if args.json:
        out = []
        for before, after, stats in program:
            item = {"name": before.name}
            for stage, f in (("before", before), ("after", after)):
                graph = interference(f)
                color = greedy_coloring(graph)
                item[stage] = {
                    "ir": f.to_json(),
                    "cfg": cfg_json(build_cfg(f.body)),
                    "interference": graph_json(graph, color, args.registers),
                    "metrics": metrics(f, args.registers),
                }
            item["rewrites"] = stats
            out.append(item)
        print(json.dumps({"functions": out}, ensure_ascii=False, indent=2))
    else:
        print_section("IR до оптимизаций", [b.text() for b, _, _ in program])
        print_section(f"IR после оптимизаций ({args.opt})", [a.text() for _, a, _ in program])
        for stage, idx in (("до", 0), ("после", 1)):
            if args.cfg or args.live:
                print_section(f"CFG {stage} оптимизаций",
                              [p[idx].name + ":\n" + cfg_text(build_cfg(p[idx].body), args.live) for p in program])
            if args.graph:
                parts = []
                for p in program:
                    graph = interference(p[idx])
                    parts.append(p[idx].name + ":\n" + graph_text(graph, greedy_coloring(graph), args.registers))
                print_section(f"граф конфликтов {stage} оптимизаций", parts)
        print_section("метрики (до -> после)", [metrics_text(b, a, s, args.registers) for b, a, s in program])

    if args.dot:
        folder = Path(args.dot)
        folder.mkdir(parents=True, exist_ok=True)
        for before, after, _ in program:
            for stage, f in (("before", before), ("after", after)):
                graph = interference(f)
                name = f"{f.name}.{stage}"
                (folder / f"{name}.cfg.dot").write_text(cfg_dot(build_cfg(f.body), name), encoding="utf-8")
                (folder / f"{name}.graph.dot").write_text(graph_dot(graph, greedy_coloring(graph), name),
                                                          encoding="utf-8")
        print(f"DOT-файлы записаны в {folder}", file=sys.stderr)
    return 0


def cmd_run(args):
    program = load(args)
    if program is None:
        return 1
    name, values = parse_call(args.call)
    if name not in [b.name for b, _, _ in program]:
        print(f"ошибка: нет функции '{name}'", file=sys.stderr)
        return 1
    res_before = run([b for b, _, _ in program], name, values)
    res_after = run([a for _, a, _ in program], name, values)
    print("до оптимизаций:    " + outcome_text(res_before))
    print("после оптимизаций: " + outcome_text(res_after))
    if res_before != res_after:
        print("результаты отличаются!", file=sys.stderr)
        return 1
    return 0


def cmd_test(args):
    from .testing import run_tests
    results = run_tests(update=args.update)
    failed = 0
    for r in results:
        if not r.ok:
            failed += 1
        if args.verbose or not r.ok:
            print(f"{'PASS' if r.ok else 'FAIL'}  [{r.group}] {r.name}")
            if r.detail:
                print(f"        {r.detail}")
    print(f"{len(results) - failed}/{len(results)} passed, {failed} failed")
    return 1 if failed else 0


def main(argv=None):
    p = argparse.ArgumentParser(prog="python3 -m ir", description="HW4: TAC, CFG, оптимизации, граф конфликтов")
    sub = p.add_subparsers(dest="cmd", required=True)

    b = sub.add_parser("build", help="IR до и после оптимизаций")
    b.add_argument("file")
    b.add_argument("--opt", default="all", help="const,alg,cse,unreach,dce | all | none (по умолчанию all)")
    b.add_argument("-O0", dest="opt", action="store_const", const="none", help="то же, что --opt none")
    b.add_argument("--cfg", action="store_true", help="показать базовые блоки и рёбра")
    b.add_argument("--live", action="store_true", help="CFG с множествами in/out")
    b.add_argument("--graph", action="store_true", help="граф конфликтов и раскраска")
    b.add_argument("--registers", type=int, help="сколько регистров есть (для подсчёта spill)")
    b.add_argument("--json", action="store_true", help="вывод в JSON")
    b.add_argument("--dot", metavar="DIR", help="сохранить CFG и графы в DOT")

    r = sub.add_parser("run", help="выполнить функцию до и после оптимизаций")
    r.add_argument("file")
    r.add_argument("call", help="например: 'sum([1, 2, 3], 3)'")
    r.add_argument("--opt", default="all")

    t = sub.add_parser("test", help="прогнать тесты")
    t.add_argument("-v", "--verbose", action="store_true")
    t.add_argument("--update", action="store_true", help="перезаписать эталоны")

    args = p.parse_args(argv)
    try:
        if args.cmd == "build":
            return cmd_build(args)
        if args.cmd == "run":
            return cmd_run(args)
        return cmd_test(args)
    except ValueError as e:
        print(f"ошибка: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
