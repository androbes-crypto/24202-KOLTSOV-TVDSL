from .gen import CompileError, generate
from .opt import ALL_PASSES, optimize, parse_passes


def compile_program(source, passes):
    # исходный текст -> [(IR до, IR после, статистика проходов)] для каждой функции
    result = []
    for f in generate(source):
        after, stats = optimize(f, passes)
        result.append((f, after, stats))
    return result


__all__ = ["ALL_PASSES", "CompileError", "compile_program", "generate", "optimize", "parse_passes"]
