# Базовые блоки, CFG, анализ живых переменных.

EXIT = "exit"


class Block:
    def __init__(self, name, instrs):
        self.name = name
        self.instrs = instrs
        self.succ = []  # [(имя блока или EXIT, "true"/"false"/"")]
        self.pred = []


def split_blocks(body):
    # Лидеры: первая инструкция, метки, инструкция после перехода или return.
    # Пару "if x goto L1; goto L2" оставляем в одном блоке, как в лекции.
    groups = []
    cur = []
    for k, ins in enumerate(body):
        if ins.op == "label" and cur:
            groups.append(cur)
            cur = []
        cur.append(ins)
        next_is_goto = k + 1 < len(body) and body[k + 1].op == "goto"
        if ins.op in ("goto", "return") or (ins.op == "if" and not next_is_goto):
            groups.append(cur)
            cur = []
    if cur:
        groups.append(cur)
    return groups


def build_cfg(body):
    blocks = []
    for n, instrs in enumerate(split_blocks(body), 1):
        blocks.append(Block(f"B{n}", instrs))
    block_of_label = {}
    for b in blocks:
        for ins in b.instrs:
            if ins.op == "label":
                block_of_label[ins.target] = b.name

    for n, b in enumerate(blocks):
        if n + 1 < len(blocks):
            next_block = blocks[n + 1].name
        else:
            next_block = EXIT
        last = b.instrs[-1]
        prev = b.instrs[-2] if len(b.instrs) >= 2 else None
        if last.op == "return":
            b.succ = [(EXIT, "")]
        elif last.op == "goto" and prev is not None and prev.op == "if":
            b.succ = [(block_of_label[prev.target], "true"), (block_of_label[last.target], "false")]
        elif last.op == "goto":
            b.succ = [(block_of_label[last.target], "")]
        elif last.op == "if":
            b.succ = [(block_of_label[last.target], "true"), (next_block, "false")]
        else:
            b.succ = [(next_block, "")]

    by_name = {b.name: b for b in blocks}
    for b in blocks:
        for s, _ in b.succ:
            if s != EXIT:
                by_name[s].pred.append(b.name)
    return blocks


def reachable(blocks):
    if not blocks:
        return set()
    by_name = {b.name: b for b in blocks}
    seen = set()
    stack = [blocks[0].name]
    while stack:
        name = stack.pop()
        if name == EXIT or name in seen:
            continue
        seen.add(name)
        for s, _ in by_name[name].succ:
            stack.append(s)
    return seen


def dominators(blocks):
    reach = reachable(blocks)
    names = [b.name for b in blocks if b.name in reach]
    by_name = {b.name: b for b in blocks}
    dom = {n: set(names) for n in names}
    if not names:
        return dom
    entry = names[0]
    dom[entry] = {entry}
    changed = True
    while changed:
        changed = False
        for n in names[1:]:
            preds = [p for p in by_name[n].pred if p in dom]
            new = set(names)
            for p in preds:
                new &= dom[p]
            new.add(n)
            if new != dom[n]:
                dom[n] = new
                changed = True
    return dom


def back_edges(blocks):
    # ребро u -> v обратное, если v доминирует над u
    dom = dominators(blocks)
    edges = []
    for b in blocks:
        for s, _ in b.succ:
            if b.name in dom and s in dom[b.name]:
                edges.append((b.name, s))
    return edges


def use_def(block):
    use = set()
    defs = set()
    for ins in block.instrs:
        for u in ins.uses():
            if u not in defs:
                use.add(u)
        defs.update(ins.defs())
    return use, defs


def liveness(blocks):
    # in(v) = use(v) ∪ (out(v) \ def(v)),  out(v) = ∪ in(s) по потомкам,  in(exit) = ∅
    live_in = {b.name: set() for b in blocks}
    live_out = {b.name: set() for b in blocks}
    ud = {b.name: use_def(b) for b in blocks}
    changed = True
    while changed:
        changed = False
        for b in reversed(blocks):
            out = set()
            for s, _ in b.succ:
                if s != EXIT:
                    out |= live_in[s]
            use, defs = ud[b.name]
            new_in = use | (out - defs)
            if out != live_out[b.name] or new_in != live_in[b.name]:
                live_out[b.name] = out
                live_in[b.name] = new_in
                changed = True
    return live_in, live_out


def live_after(block, out):
    # живые переменные сразу после каждой инструкции блока
    live = set(out)
    result = [None] * len(block.instrs)
    for k in range(len(block.instrs) - 1, -1, -1):
        result[k] = set(live)
        ins = block.instrs[k]
        live -= set(ins.defs())
        live |= set(ins.uses())
    return result


def edge_text(succ):
    parts = []
    for s, kind in succ:
        parts.append(f"{s} ({kind})" if kind else s)
    return ", ".join(parts)


def cfg_text(blocks, show_live=False):
    lines = []
    if show_live:
        live_in, live_out = liveness(blocks)
    reach = reachable(blocks)
    for b in blocks:
        mark = ""
        if b is blocks[0]:
            mark = " [вход]"
        elif b.name not in reach:
            mark = " [недостижим]"
        lines.append(f"{b.name}{mark}  pred: {', '.join(b.pred) or '—'}  succ: {edge_text(b.succ)}")
        if show_live:
            lines.append("  in:  {" + ", ".join(sorted(live_in[b.name])) + "}")
        for ins in b.instrs:
            lines.append(("  " if ins.op == "label" else "    ") + str(ins))
        if show_live:
            lines.append("  out: {" + ", ".join(sorted(live_out[b.name])) + "}")
    edges = back_edges(blocks)
    if edges:
        lines.append("обратные рёбра: " + ", ".join(f"{u} -> {v}" for u, v in edges))
    return "\n".join(lines) + "\n"


def cfg_json(blocks):
    live_in, live_out = liveness(blocks)
    res = []
    for b in blocks:
        res.append({
            "name": b.name,
            "instrs": [str(i) for i in b.instrs],
            "succ": [{"to": s, "kind": k} for s, k in b.succ],
            "pred": b.pred,
            "live_in": sorted(live_in[b.name]),
            "live_out": sorted(live_out[b.name]),
        })
    return {"blocks": res, "back_edges": [list(e) for e in back_edges(blocks)]}


def cfg_dot(blocks, title):
    lines = [f'digraph "{title}" {{', '  node [shape=box, fontname="monospace"];', "  exit [shape=oval];"]
    for b in blocks:
        text = "\\l".join(str(i).replace('"', '\\"') for i in b.instrs)
        lines.append(f'  {b.name} [label="{b.name}\\l{text}\\l"];')
    back = back_edges(blocks)
    for b in blocks:
        for s, kind in b.succ:
            attrs = []
            if kind:
                attrs.append(f'label="{kind}"')
            if (b.name, s) in back:
                attrs.append("style=dashed")
            line = f"  {b.name} -> {s}"
            if attrs:
                line += " [" + ", ".join(attrs) + "]"
            lines.append(line + ";")
    lines.append("}")
    return "\n".join(lines) + "\n"
