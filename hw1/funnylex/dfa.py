from collections import deque, defaultdict
from dataclasses import dataclass
from typing import Optional

from .nfa import NFA

NON_ASCII = "NON_ASCII"


def char_classes(nfa: NFA) -> list[frozenset]:
    blocks = [frozenset(range(128))]
    for cs in {cs for edges in nfa.edges for cs, _ in edges}:
        nxt = []
        for b in blocks:
            inside, outside = b & cs, b - cs
            nxt.extend([inside, outside] if inside and outside else [b])
        blocks = nxt
    return sorted(blocks, key=min)


@dataclass
class DFA:
    delta: list[list[int]]
    label: list[Optional[int]]
    start: int
    trap: int

    @property
    def n(self):
        return len(self.delta)

    @property
    def k(self):
        return len(self.delta[0])


def _closure(nfa: NFA, states) -> frozenset:
    seen, stack = set(states), list(states)
    while stack:
        for t in nfa.eps[stack.pop()]:
            if t not in seen:
                seen.add(t)
                stack.append(t)
    return frozenset(seen)


def subset_construction(nfa: NFA, classes: list[frozenset]) -> DFA:
    reps = [min(c) for c in classes]
    dead = frozenset()
    start = _closure(nfa, [nfa.start])
    ids = {start: 0, dead: 1}
    order = [start, dead]
    delta = []
    i = 0
    while i < len(order):
        S = order[i]
        row = []
        for r in reps:
            T = {t for s in S for cs, t in nfa.edges[s] if r in cs}
            T = _closure(nfa, T) if T else dead
            if T not in ids:
                ids[T] = len(order)
                order.append(T)
            row.append(ids[T])
        row.append(ids[dead])
        delta.append(row)
        i += 1
    label = []
    for S in order:
        acc = [nfa.accept[s] for s in S if s in nfa.accept]
        label.append(min(acc) if acc else None)
    return DFA(delta, label, 0, ids[dead])


def hopcroft(d: DFA) -> DFA:
    n, k = d.n, d.k
    inv = [[[] for _ in range(n)] for _ in range(k)]
    for s in range(n):
        for a in range(k):
            inv[a][d.delta[s][a]].append(s)

    groups = defaultdict(set)
    for s in range(n):
        groups[d.label[s]].add(s)
    blocks = list(groups.values())
    block_of = [0] * n
    for b, members in enumerate(blocks):
        for s in members:
            block_of[s] = b

    work, in_work = deque(), set()

    def push(b, a):
        if (b, a) not in in_work:
            in_work.add((b, a))
            work.append((b, a))

    for b in range(len(blocks)):
        for a in range(k):
            push(b, a)

    while work:
        b, a = work.popleft()
        in_work.discard((b, a))
        X = set()
        for q in blocks[b]:
            X.update(inv[a][q])
        touched = defaultdict(set)
        for p in X:
            touched[block_of[p]].add(p)
        for y, inter in touched.items():
            if len(inter) == len(blocks[y]):
                continue
            rest = blocks[y] - inter
            blocks[y] = inter
            z = len(blocks)
            blocks.append(rest)
            for s in rest:
                block_of[s] = z
            for c in range(k):
                if (y, c) in in_work:
                    push(z, c)
                else:
                    push(y if len(blocks[y]) <= len(blocks[z]) else z, c)

    new_id = {block_of[d.start]: 0}
    q = deque([block_of[d.start]])
    while q:
        b = q.popleft()
        rep = next(iter(blocks[b]))
        for a in range(k):
            t = block_of[d.delta[rep][a]]
            if t not in new_id:
                new_id[t] = len(new_id)
                q.append(t)
    delta = [None] * len(new_id)
    label = [None] * len(new_id)
    for b, nid in new_id.items():
        rep = next(iter(blocks[b]))
        delta[nid] = [new_id[block_of[d.delta[rep][a]]] for a in range(k)]
        label[nid] = d.label[rep]
    return DFA(delta, label, 0, new_id[block_of[d.trap]])


def equivalent(d1: DFA, d2: DFA) -> bool:
    seen = {(d1.start, d2.start)}
    q = deque(seen)
    while q:
        s1, s2 = q.popleft()
        if d1.label[s1] != d2.label[s2]:
            return False
        for a in range(d1.k):
            p = (d1.delta[s1][a], d2.delta[s2][a])
            if p not in seen:
                seen.add(p)
                q.append(p)
    return True


def moore_state_count(d: DFA) -> int:
    part = {}
    cls = [part.setdefault(l, len(part)) for l in d.label]
    while True:
        sigs = {}
        new = [sigs.setdefault((cls[s], tuple(cls[t] for t in d.delta[s])), len(sigs))
               for s in range(d.n)]
        if len(sigs) == len(set(cls)):
            return len(sigs)
        cls = new


def run(d: DFA, char_to_class: list[int], text: str) -> int:
    s = d.start
    for ch in text:
        o = ord(ch)
        s = d.delta[s][char_to_class[o] if o < 128 else d.k - 1]
    return s
