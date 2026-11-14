import json
import os
import random
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from sema import check
from sema.testing import TESTS, load_cases, run
from funny import dumps


class Cases(unittest.TestCase):
    def test_positive_and_negative(self):
        failed = [f"{r.name}: {r.detail}" for r in run() if not r.ok]
        self.assertEqual(failed, [])


class AnnotatedAst(unittest.TestCase):
    def test_types_in_json(self):
        ast, diags, _ = check("function f(a: int[]) returns (r: bool)\n{\n  var n = length(a);\n  r = n > 0;\n}\n")
        self.assertEqual(diags, [])
        data = json.loads(dumps(ast))
        fn = data["functions"][0]
        self.assertEqual(fn["signature"], "(int[]) -> (bool)")
        decl, assign = fn["body"]["stmts"]
        self.assertEqual((decl["type"], decl["inferred"]), ("int", True))
        self.assertEqual(decl["init"]["type"], "int")
        self.assertEqual(decl["init"]["array"]["ref"], "param")
        self.assertEqual(assign["value"]["type"], "bool")
        self.assertEqual(assign["value"]["left"]["decl"], "3:3")

    def test_errors_have_positions(self):
        for case in load_cases(TESTS / "negative.txt"):
            _, diags, _ = check(case["text"])
            for d in diags:
                self.assertGreater(d.line, 0)
                self.assertGreater(d.col, 0)
                self.assertTrue(d.message)

    def test_no_crash_on_mutated_programs(self):
        rnd = random.Random(2026)
        programs = [c["text"] for name in ("positive.txt", "negative.txt") for c in load_cases(TESTS / name)]
        words = ["x", "n", "a", "r", "true", "1", "+", "==", "&&", "[", "]", "(", ")", "f", "var", "=", ";", "!"]
        for _ in range(2000):
            toks = rnd.choice(programs).split(" ")
            for _ in range(rnd.randint(1, 4)):
                toks[rnd.randrange(len(toks))] = rnd.choice(words)
            check(" ".join(toks))


if __name__ == "__main__":
    unittest.main()
