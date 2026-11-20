"""Отпечаток по «случайному числу» (по работе «One Token Is Enough», arXiv:2607.10252).

Просим модель назвать случайное число 1–100 много раз. У каждой модели своё
очень неравномерное распределение (кто-то любит 42, кто-то 37, 73).
Распределение одной и той же модели стабильно, у разных — заметно отличается.
Сравниваем с эталоном по дивергенции Йенсена–Шеннона (JSD).
"""
from __future__ import annotations

import math
import re
from collections import Counter

from ...core import baselines
from ...core.check import Check, register
from ...core.types import Finding, Status

PROMPTS = ["Назови случайное число от 1 до 100. Только число.",
           "Name a random number between 1 and 100. Number only."]
N_PER_PROMPT = 15


def sample(client, model, n=N_PER_PROMPT) -> Counter:
    c = Counter()
    for p in PROMPTS:
        for _ in range(n):
            r = client.chat(model, [{"role": "user", "content": p}], max_tokens=8, temperature=1.0)
            m = re.search(r"\d{1,3}", r.text) if r.ok else None
            if m:
                c[f"{p[:2]}:{int(m.group())}"] += 1
    return c


def jsd(a: Counter, b: Counter) -> float:
    keys = set(a) | set(b)
    sa, sb = sum(a.values()) or 1, sum(b.values()) or 1
    eps = 1e-9

    def kl(p, q):
        return sum(p[k] * math.log2((p[k] + eps) / (q[k] + eps)) for k in keys if p[k] > 0)
    pa = {k: a.get(k, 0) / sa for k in keys}
    pb = {k: b.get(k, 0) / sb for k in keys}
    m = {k: (pa[k] + pb[k]) / 2 for k in keys}
    return (kl(pa, m) + kl(pb, m)) / 2


@register
class RandomNumber(Check):
    name = "random_number"
    title = "Отпечаток «случайного числа»"
    level = 3   # ~30 запросов, только в полном режиме

    def run(self, client, target, maker):
        got = sample(client, target.model)
        if sum(got.values()) < 10:
            return [Finding(self.name, Status.SKIP, self.title, "Мало ответов для статистики.")]
        top = ", ".join(f"{k.split(':')[1]}×{v}" for k, v in got.most_common(4))
        bases = baselines.load("numbers")
        if not bases:
            return [Finding(self.name, Status.INFO, self.title, f"Любимые числа: {top}. Эталонов нет.",
                            evidence={"numbers": dict(got)})]
        ranked = sorted((jsd(got, Counter(v["numbers"])), n, v) for n, v in bases.items())
        d, name, best = ranked[0]
        ev = {"closest": name, "jsd": round(d, 3), "top": top}
        if best.get("maker") == maker and d < 0.35:
            return [Finding(self.name, Status.PASS, self.title, f"Распределение похоже на эталон {name} (JSD {d:.2f}).", evidence=ev)]
        if best.get("maker") != maker and d < 0.25:
            return [Finding(self.name, Status.FAIL, self.title,
                            f"Числа выбирает как {name} ({best['maker']}), JSD {d:.2f}.", evidence=ev)]
        return [Finding(self.name, Status.INFO, self.title, f"Ближайший эталон {name} (JSD {d:.2f}). Любимые: {top}.", evidence=ev)]
