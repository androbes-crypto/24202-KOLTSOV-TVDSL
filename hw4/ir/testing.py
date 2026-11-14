# Прогон тестов из tests/.
#   ir.txt   — программа и ожидаемый IR после всех оптимизаций
#   run.txt  — программа и вызовы с ожидаемым результатом (проверяются до и после оптимизаций)
#   кроме того, все программы (и positive.txt из HW3) запускаются на случайных входах:
#   результат без оптимизаций должен совпасть с результатом после каждой оптимизации.
import random
from pathlib import Path

from . import compile_program
from .gen import HW3, generate
from .interp import TOO_LONG, UNINIT, outcome_text, parse_call, run
from .opt import ALL_PASSES, optimize

TESTS = Path(__file__).resolve().parent.parent / "tests"


class Result:
    def __init__(self, group, name, ok, detail=""):
        self.group = group
        self.name = name
        self.ok = ok
        self.detail = detail


def load_cases(path):
    cases = []
    case = None
    section = None
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("=== "):
            case = {"name": line[4:].strip(), "program": [], "expected": []}
            cases.append(case)
            section = "program"
        elif line.startswith("--- ") and case is not None:
            section = "expected"
        elif case is not None:
            case[section].append(line)
    for case in cases:
        for key in ("program", "expected"):
            while case[key] and not case[key][-1].strip():
                case[key].pop()
    return cases


def save_cases(path, cases):
    parts = []
    for case in cases:
        parts.append(f"=== {case['name']}\n" + "\n".join(case["program"]) + "\n--- ожидается\n"
                     + "\n".join(case["expected"]) + "\n")
    path.write_text("\n".join(parts), encoding="utf-8")


def source(case):
    return "\n".join(case["program"]) + "\n"


def check_ir(update):
    results = []
    path = TESTS / "ir.txt"
    cases = load_cases(path)
    for case in cases:
        program = compile_program(source(case), ALL_PASSES)
        got = "\n".join(after.text() for _, after, _ in program).rstrip("\n").splitlines()
        if update:
            case["expected"] = got
        ok = got == case["expected"]
        detail = "" if ok else first_diff(case["expected"], got)
        results.append(Result("ir", case["name"], ok, detail))
    if update:
        save_cases(path, cases)
    return results


def check_run(update):
    results = []
    path = TESTS / "run.txt"
    cases = load_cases(path)
    for case in cases:
        program = compile_program(source(case), ALL_PASSES)
        before = [b for b, _, _ in program]
        after = [a for _, a, _ in program]
        new_expected = []
        errors = []
        for line in case["expected"]:
            call = line.split(" = ")[0]
            want = line.split(" = ", 1)[1] if " = " in line else ""
            name, args = parse_call(call)
            got1 = outcome_text(run(before, name, args))
            got2 = outcome_text(run(after, name, args))
            new_expected.append(f"{call} = {got1}")
            if got1 != want:
                errors.append(f"{call}: ожидалось {want}, без оптимизаций {got1}")
            if got2 != got1:
                errors.append(f"{call}: без оптимизаций {got1}, после {got2}")
        if update:
            case["expected"] = new_expected
            errors = [e for e in errors if "после" in e]
        results.append(Result("run", case["name"], not errors, "; ".join(errors)))
    if update:
        save_cases(path, cases)
    return results


def random_value(type_, rnd):
    if type_ == "int":
        return rnd.randint(-3, 6)
    if type_ == "bool":
        return rnd.random() < 0.5
    elem = type_[:-2]
    return tuple(random_value(elem, rnd) for _ in range(rnd.randint(0, 4)))


def check_equivalence(rnd, tries=30):
    programs = []
    for name in ("ir.txt", "run.txt"):
        for case in load_cases(TESTS / name):
            programs.append((case["name"], source(case)))
    hw3_positive = HW3 / "tests" / "positive.txt"
    if hw3_positive.exists():
        for case in load_cases(hw3_positive):
            programs.append(("HW3: " + case["name"], source(case)))

    variants = [[p] for p in ALL_PASSES] + [ALL_PASSES]
    results = []
    for title, text in programs:
        funcs = generate(text)
        errors = []
        for passes in variants:
            optimized = [optimize(f, passes)[0] for f in funcs]
            for f in funcs:
                for _ in range(tries):
                    args = [random_value(t, rnd) for _, t in f.params]
                    r1 = run(funcs, f.name, args)
                    if r1[0] == "error" and r1[1] in (UNINIT, TOO_LONG):
                        continue  # неопределённое поведение — сравнивать нечего
                    r2 = run(optimized, f.name, args)
                    if r1 != r2:
                        errors.append(f"{'+'.join(passes)}: {f.name}{args}: {outcome_text(r1)} != {outcome_text(r2)}")
        results.append(Result("eq", title, not errors, "; ".join(errors[:3])))
    return results


def first_diff(expected, got):
    for n, (a, b) in enumerate(zip(expected, got), 1):
        if a != b:
            return f"строка {n}:\n        ожидалось: {a}\n        получено:  {b}"
    return f"разная длина: ожидалось {len(expected)} строк, получено {len(got)}"


def run_tests(update=False):
    return check_ir(update) + check_run(update) + check_equivalence(random.Random(2026))
