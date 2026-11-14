import io
import json
import os
import sys
import unittest
from contextlib import redirect_stdout

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from ir import compile_program, generate, optimize, parse_passes
from ir.__main__ import main
from ir.cfg import back_edges, build_cfg
from ir.regs import greedy_coloring, interference
from ir.testing import TESTS, load_cases, run_tests, source

LECTURE = """function f(x: int, a: int[]) returns (r: int)
{
  if (x > 0) { r = a[x] + 1; } else { r = 0; }
}
"""

LOOP = """function f(n: int) returns (r: int)
{
  var i = 0;
  r = 0;
  while (i < n) { r = r + i; i = i + 1; }
}
"""


def all_programs():
    for name in ("ir.txt", "run.txt"):
        for case in load_cases(TESTS / name):
            yield source(case)


class Cases(unittest.TestCase):
    def test_all_cases(self):
        failed = [f"{r.name}: {r.detail}" for r in run_tests() if not r.ok]
        self.assertEqual(failed, [])


class Cfg(unittest.TestCase):
    def test_lecture_example(self):
        # лекция 6, слайд 11: четыре блока, b1 -> b2/b3 -> b4
        blocks = build_cfg(generate(LECTURE)[0].body)
        self.assertEqual(len(blocks), 4)
        self.assertEqual(blocks[0].succ, [("B2", "true"), ("B3", "false")])
        self.assertEqual(blocks[1].succ, [("B4", "")])
        self.assertEqual(blocks[2].succ, [("B4", "")])
        self.assertEqual(blocks[3].pred, ["B2", "B3"])

    def test_back_edge_of_while(self):
        blocks = build_cfg(generate(LOOP)[0].body)
        self.assertEqual(back_edges(blocks), [("B3", "B2")])


class Coloring(unittest.TestCase):
    def test_neighbours_have_different_colors(self):
        for text in all_programs():
            for f in generate(text):
                for g in (f, optimize(f, parse_passes("all"))[0]):
                    graph = interference(g)
                    color = greedy_coloring(graph)
                    for a in graph:
                        for b in graph[a]:
                            self.assertNotEqual(color[a], color[b], f"{g.name}: {a} и {b}")

    def test_conflicting_temps(self):
        f = generate("function f(a: int, b: int, c: int) returns (r: int)\n{\n  r = (a + b) * (b + c);\n}\n")[0]
        graph = interference(f)
        self.assertIn("t2", graph["t1"])        # t1 = a + b ещё нужна, когда считается t2 = b + c
        self.assertEqual(len(set(greedy_coloring(graph).values())), 2)


class Flags(unittest.TestCase):
    def test_no_passes_keeps_ir(self):
        for text in all_programs():
            for before, after, _ in compile_program(text, []):
                self.assertEqual(before.text(), after.text())

    def test_optimizations_do_not_grow_code(self):
        for text in all_programs():
            for before, after, _ in compile_program(text, parse_passes("all")):
                self.assertLessEqual(after.instr_count(), before.instr_count())

    def test_single_pass(self):
        f = generate("function f(x: int) returns (r: int)\n{\n  r = x * 1;\n}\n")[0]
        only_const = optimize(f, ["const"])[0]
        only_alg = optimize(f, ["alg"])[0]
        self.assertIn("r := x * 1", only_const.text())
        self.assertIn("r := x\n", only_alg.text())

    def test_unknown_pass(self):
        with self.assertRaises(ValueError):
            parse_passes("const,magic")


class Json(unittest.TestCase):
    def test_json_output(self):
        path = os.path.join(ROOT, "examples", "lecture.fun")
        out = io.StringIO()
        with redirect_stdout(out):
            code = main(["build", "--json", path])
        self.assertEqual(code, 0)
        data = json.loads(out.getvalue())
        f = data["functions"][0]
        self.assertEqual(f["name"], "f")
        first = f["before"]["ir"]["body"][0]
        self.assertEqual(first, {"op": "binop", "dst": "t1", "sym": ">",
                                 "args": [{"var": "x"}, {"int": 0}]})
        self.assertEqual(f["before"]["ir"]["vars"]["t1"], {"type": "bool", "temp": True})
        self.assertEqual(len(f["after"]["cfg"]["blocks"]), 4)
        self.assertIn("colors", f["after"]["interference"])


if __name__ == "__main__":
    unittest.main()
