# Граф конфликтов временных и жадная раскраска (лекция 6, слайды 38-39).

from .cfg import build_cfg, live_after, liveness


def temp_number(name):
    return int(name[1:])


def interference(f):
    # вершины — временные; ребро, если одна определяется, пока другая жива
    temps = set()
    for ins in f.body:
        temps.update(t for t in ins.defs() + ins.uses() if t in f.temps)
    graph = {t: set() for t in temps}
    blocks = build_cfg(f.body)
    _, live_out = liveness(blocks)
    for b in blocks:
        after = live_after(b, live_out[b.name])
        for ins, live in zip(b.instrs, after):
            for d in ins.defs():
                if d not in graph:
                    continue
                for v in live:
                    if v != d and v in graph:
                        graph[d].add(v)
                        graph[v].add(d)
    return graph


def greedy_coloring(graph):
    # по убыванию степени; каждой вершине — наименьший цвет, которого нет у соседей
    order = sorted(graph, key=lambda t: (-len(graph[t]), temp_number(t)))
    color = {}
    for t in order:
        busy = {color[n] for n in graph[t] if n in color}
        c = 0
        while c in busy:
            c += 1
        color[t] = c
    return color


def colors_count(color):
    if not color:
        return 0
    return max(color.values()) + 1


def spilled(color, registers):
    # если регистров меньше, чем цветов, лишние цвета уходят в память (на стек)
    if registers is None:
        return []
    return sorted([t for t, c in color.items() if c >= registers], key=temp_number)


def edges(graph):
    res = []
    for a in graph:
        for b in graph[a]:
            if temp_number(a) < temp_number(b):
                res.append((a, b))
    return sorted(res, key=lambda e: (temp_number(e[0]), temp_number(e[1])))


def graph_text(graph, color, registers=None):
    lines = [f"вершин: {len(graph)}, рёбер: {len(edges(graph))}"]
    in_memory = spilled(color, registers)
    for t in sorted(graph, key=temp_number):
        where = "память" if t in in_memory else f"r{color[t]}"
        neighbours = ", ".join(sorted(graph[t], key=temp_number)) or "—"
        lines.append(f"  {t:<5} {where:<7} соседи: {neighbours}")
    line = f"цветов: {colors_count(color)}"
    if in_memory:
        line += f"; не хватило регистров ({registers}): {', '.join(in_memory)} в памяти"
    lines.append(line)
    return "\n".join(lines) + "\n"


def graph_json(graph, color, registers=None):
    return {
        "nodes": sorted(graph, key=temp_number),
        "edges": [list(e) for e in edges(graph)],
        "coloring": color,
        "colors": colors_count(color),
        "spilled": spilled(color, registers),
    }


def graph_dot(graph, color, title):
    palette = ["#8dd3c7", "#ffffb3", "#bebada", "#fb8072", "#80b1d3", "#fdb462", "#b3de69", "#fccde5"]
    lines = [f'graph "{title}" {{', "  node [shape=circle, style=filled];"]
    for t in sorted(graph, key=temp_number):
        fill = palette[color[t] % len(palette)]
        lines.append(f'  {t} [label="{t}\\nr{color[t]}", fillcolor="{fill}"];')
    for a, b in edges(graph):
        lines.append(f"  {a} -- {b};")
    lines.append("}")
    return "\n".join(lines) + "\n"
