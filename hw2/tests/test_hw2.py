import json
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from funny import dumps, parse
from funny.ll1 import load_bnf, analyze
from funny.testing import run_fuzz, run_snapshots


class Snapshots(unittest.TestCase):
    def test_snapshots(self):
        failed = [f"{r.name}: {r.detail}" for r in run_snapshots() if not r.ok]
        self.assertEqual(failed, [])

    def test_no_infinite_loop(self):
        r = run_fuzz(1000)
        self.assertTrue(r.ok, r.detail)


class Api(unittest.TestCase):
    def test_json_roundtrip(self):
        ast, diags = parse("function f(a: int[]) returns () { a[0] = 1; }")
        self.assertEqual(diags, [])
        data = json.loads(dumps(ast))
        assign = data["functions"][0]["body"]["stmts"][0]
        self.assertEqual(assign["kind"], "Assign")
        self.assertEqual(assign["sugar"], "array-update")
        self.assertEqual(assign["value"]["kind"], "Update")

    def test_positions(self):
        _, diags = parse("function f() returns ()\n{\n  x = ;\n}\n")
        self.assertEqual([(d.line, d.col) for d in diags], [(3, 7)])

    def test_grammar_is_ll1(self):
        rules, start = load_bnf()
        conflicts = analyze(rules, start)[2]
        self.assertEqual([(a, t) for a, t, _ in conflicts], [("else_part", "'else'")])


if __name__ == "__main__":
    unittest.main()
