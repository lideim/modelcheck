"""Отпечаток «сорок вопросов»: однословные ответы на бытовые вопросы.

По работе «Forty Questions» (Parikh, arXiv:2610.28281): каждая модель отвечает на
«Назови цвет», «Назови поэта», «Назови звук» со своими устойчивыми привычками
(кто-то говорит «лаванда», кто-то «синий»). 40 ответов определяют точную модель
в 92,5% случаев. Особенно полезно для открытых моделей (Llama, Qwen, Gemma, Mistral):
их чаще всего подменяют, квантуют и запускают с неофициальным шаблоном.

Без эталонов проверка только сохраняет «профиль ответов». С эталоном
(modelcheck baseline … --numbers) — сравнивает по правдоподобию.
"""
from __future__ import annotations

import math
import re
from collections import Counter

from ...core import baselines
from ...core.check import Check, register
from ...core.types import Finding, Status

QUESTIONS = ["Name a color.", "Name a fruit.", "Name a poet.", "Name a sound.", "Name a city.",
             "Name an animal.", "Name a flower.", "Name a musical instrument.", "Name a planet.", "Name a gemstone."]
REPEATS = 4


def ask_all(client, model, repeats=REPEATS) -> dict[str, Counter]:
    prof: dict[str, Counter] = {}
    for q in QUESTIONS:
        c = Counter()
        for _ in range(repeats):
            r = client.chat(model, [{"role": "user", "content": q + " Answer with one word only."}],
                            max_tokens=6, temperature=1.0)
            if r.ok:
                w = re.sub(r"[^a-z]", "", r.text.strip().split()[0].lower()) if r.text.strip() else ""
                if w:
                    c[w] += 1
        prof[q] = c
    return prof


def loglik(prof: dict[str, Counter], ref: dict[str, dict]) -> float:
    """Среднее log-правдоподобие ответов endpoint'а под профилем эталона (сглаживание Лапласа)."""
    total, n = 0.0, 0
    for q, cnt in prof.items():
        refc = Counter(ref.get(q, {}))
        s = sum(refc.values()) + 1 + len(refc)
        for w, k in cnt.items():
            total += k * math.log((refc.get(w, 0) + 1) / s)
            n += k
    return total / max(n, 1)


@register
class FortyQuestions(Check):
    name = "forty_questions"
    title = "Отпечаток «сорок вопросов»"
    level = 3

    def run(self, client, target, maker):
        prof = ask_all(client, target.model)
        answered = sum(sum(c.values()) for c in prof.values())
        if answered < len(QUESTIONS) * 2:
            return [Finding(self.name, Status.SKIP, self.title, "Мало ответов.")]
        favs = ", ".join(c.most_common(1)[0][0] for c in prof.values() if c)
        bases = baselines.load("forty")
        ev = {"profile": {q: dict(c) for q, c in prof.items()}}
        if not bases:
            return [Finding(self.name, Status.INFO, self.title, f"Привычные ответы: {favs}. Эталонов нет.", evidence=ev)]
        ranked = sorted(((loglik(prof, v["forty"]), n, v) for n, v in bases.items()), reverse=True)
        best_ll, best_name, best = ranked[0]
        own = max((ll for ll, n, v in ranked if v.get("maker") == maker), default=None)
        ev.update(closest=best_name, loglik=round(best_ll, 3))
        if best.get("maker") == maker:
            return [Finding(self.name, Status.PASS, self.title, f"Ответы ближе всего к эталону {best_name}.", evidence=ev)]
        if own is not None and best_ll - own > 0.7:
            return [Finding(self.name, Status.FAIL, self.title,
                            f"Ответы гораздо ближе к {best_name} ({best['maker']}), чем к {maker}.", evidence=ev)]
        return [Finding(self.name, Status.INFO, self.title, f"Ближайший эталон {best_name}; разница с {maker} мала.", evidence=ev)]
