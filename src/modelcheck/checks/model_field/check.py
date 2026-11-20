"""Совпадает ли модель в ответе с запрошенной.

Схемы: просили Opus — в поле model пришёл Haiku (подмена уровня);
просили Claude — пришёл qwen/gpt (подмена бренда). Плюс просим
несуществующую модель: честный API отказывает, а перепродавец
часто молча отвечает «чем-нибудь».
"""
from __future__ import annotations

import re

from ...core.check import Check, register
from ...makers import maker_of, profile, tier_of
from ...core.types import Finding, Status


def _norm(s: str) -> str:
    s = s.lower().split("/")[-1]
    return re.sub(r"[^a-z0-9]", "", s)


@register
class ModelField(Check):
    name = "model_field"
    title = "Поле model и фантомная модель"
    level = 1

    def run(self, client, target, maker):
        out = []
        r = client.chat(target.model, [{"role": "user", "content": "Скажи «ок»."}], max_tokens=20)
        if not r.ok:
            # недоступный сервис — не улика подмены: отчёт получит вердикт «нет данных»
            return [Finding(self.name, Status.SKIP, self.title,
                            f"Сервис не ответил ({r.status or 'сеть'}: {r.error[:100]}). Проверить модель нельзя.",
                            evidence={"unavailable": True})]

        got = r.model or ""
        if not got:
            out.append(Finding(self.name, Status.WARN, self.title, "В ответе нет поля model."))
        else:
            gm = maker_of(got)
            if gm not in ("unknown", maker):
                out.append(Finding(self.name, Status.FAIL, self.title,
                                   f"Запрошен {target.model}, а ответ подписан моделью {got} ({gm}).",
                                   critical=True, evidence={"model": got}))
            else:
                want_t, got_t = tier_of(target.model, maker), tier_of(got, maker)
                tiers = profile(maker).tiers
                if want_t and got_t and want_t != got_t and tiers.index(got_t) > tiers.index(want_t):
                    out.append(Finding(self.name, Status.FAIL, self.title,
                                       f"Подмена уровня: запрошен {want_t}, отвечает {got_t} ({got}).",
                                       critical=True, evidence={"model": got}))
                elif _norm(target.model) in _norm(got) or _norm(got) in _norm(target.model):
                    out.append(Finding(self.name, Status.PASS, self.title, f"Ответ подписан той же моделью: {got}."))
                else:
                    out.append(Finding(self.name, Status.WARN, self.title,
                                       f"Имя в ответе отличается: {got} (запрошен {target.model})."))

        fake = target.model.split("/")[0] + "/" if "/" in target.model else ""
        p = client.chat(fake + "nonexistent-model-zz9", [{"role": "user", "content": "hi"}], max_tokens=5)
        if p.ok:
            out.append(Finding(self.name, Status.FAIL, "Фантомная модель",
                               f"Запрос к несуществующей модели получил ответ (model={p.model or '—'}). "
                               "Посредник подсовывает что попало.", evidence={"model": p.model}))
        else:
            out.append(Finding(self.name, Status.PASS, "Фантомная модель", "Несуществующая модель честно отклонена."))
        return out
