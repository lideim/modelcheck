"""Поведенческие ловушки: личность, чужие стоп-токены, утечка китайского, свой системный промпт.

Слабые сигналы по отдельности (системный промпт может заставить модель назваться
кем угодно), но в сумме ловят грубую подмену:
- у каждой модели с открытыми весами свои служебные токены (DeepSeek
  <｜end▁of▁sentence｜>, Llama <|eot_id|>, Qwen <|im_end|>…). Модель «узнаёт»
  СВОЙ токен и обрывается на нём, чужой повторяет как обычный текст;
- китайская модель под чужим именем иногда отвечает иероглифами;
- перепродавец вшивает свой системный промпт и игнорирует наш.
"""
from __future__ import annotations

import re

from ...core import rand
from ...core.check import Check, register
from ...core.types import Finding, Status, svc
from ...makers import PROFILES, named_makers, profile

# много формулировок: в каждом прогоне берём 3 случайные (RU + EN обязательно)
ASKS_RU = ["Какая ты модель и какая компания тебя создала? Ответь кратко.",
           "Назови разработчика своей нейросети одним словом.",
           "Кто тебя обучил? Одной фразой.",
           "На какой модели ты работаешь и чья она?",
           "Как называется компания, которая тебя сделала?"]
ASKS_EN = ["Who trained you? One short sentence.",
           "Which company built the model I'm talking to? Be brief.",
           "What model are you, and who made it?",
           "Name the lab that created you, one word."]
FRUITS = ["Перечисли через запятую 5 фруктов на русском. Только список.",
          "Назови 4 города России через запятую. Только список.",
          "Перечисли 5 цветов радуги по-русски, через запятую."]
REPEAT = ["Повтори дословно в кавычках: \"{a}{tok}{b}\"", "Скопируй строку без изменений: {a}{tok}{b}",
          "Выведи ровно этот текст: «{a}{tok}{b}»"]


@register
class Identity(Check):
    name = "identity"
    title = "Личность и поведенческие ловушки"
    level = 1

    def run(self, client, target, maker):
        return [*self._who(client, target, maker), *self._stop_tokens(client, target, maker),
                *self._cjk(client, target, maker), *self._system(client, target)]

    def _who(self, client, target, maker):
        named, ok, answers = {}, 0, []
        asks = [rand.pick(ASKS_RU), rand.pick(ASKS_EN), rand.pick(ASKS_RU)]
        for q in asks:
            r = client.chat(target.model, [{"role": "user", "content": rand.cover(q)}], max_tokens=60, temperature=0)
            if r.ok:
                ok += 1
                answers.append(r.text[:80])
                for m in named_makers(r.text):
                    named[m] = named.get(m, 0) + 1
        foreign = {m: c for m, c in named.items() if m != maker}
        ev = {"named": named, "answers": answers}
        if not ok:
            return [Finding(self.name, Status.SKIP, "Кто ты?", "Ответов нет.")]
        if foreign and not named.get(maker):
            return [Finding(self.name, Status.FAIL, "Кто ты?",
                            f"Модель называет себя продуктом {', '.join(foreign)}, а не {maker}.", evidence=ev)]
        if foreign:
            return [Finding(self.name, Status.WARN, "Кто ты?",
                            f"Путается: на одни вопросы называет {maker}, на другие — {', '.join(foreign)}. "
                            "Так бывает, когда поверх другой модели вшит промпт «ты — заявленная модель».", evidence=ev)]
        if named.get(maker):
            return [Finding(self.name, Status.PASS, "Кто ты?", f"Стабильно называет себя {maker} ({named[maker]}/{ok}).")]
        return [Finding(self.name, Status.INFO, "Кто ты?", "Уходит от ответа — сам по себе не признак.", evidence=ev)]

    def _stop_tokens(self, client, target, maker):
        """Служебные токены чужих семейств: модель обрывается только на своём."""
        own = set(profile(maker).special_tokens)
        probes: dict[str, str] = {}
        for p in PROFILES.values():
            if p.name != maker and p.special_tokens and p.special_tokens[0] not in own:
                probes.setdefault(p.special_tokens[0], p.name)
        hits, answered = [], 0
        for tok, fam in rand.shuffle(list(probes.items())):
            a, b = rand.word(3).split("-")[0], rand.word(3).split("-")[0]
            q = rand.pick(REPEAT).format(a=a, tok=tok, b=b)
            r = client.chat(target.model, [{"role": "user", "content": q}], max_tokens=40, temperature=0)
            if not r.ok:
                continue
            answered += 1
            if a in r.text and b not in r.text:
                hits.append(fam)
        if hits:
            return [Finding(self.name, Status.FAIL, "Чужие стоп-токены",
                            f"Ответ обрывается на служебном токене {', '.join(hits)}: так ведёт себя модель этого семейства.",
                            evidence={"families": hits})]
        if answered:
            return [Finding(self.name, Status.PASS, "Чужие стоп-токены",
                            f"Служебные токены {answered} чужих семейств восприняты как обычный текст.")]
        return []

    def _cjk(self, client, target, maker):
        if profile(maker).cjk_native:
            return []
        r = client.chat(target.model, [{"role": "user", "content": rand.pick(FRUITS)}], max_tokens=60, temperature=0)
        if r.ok and re.search(r"[\u4e00-\u9fff]", r.text):
            return [Finding(self.name, Status.FAIL, "Утечка китайского",
                            "В русском ответе появились иероглифы — типичный след китайской модели.",
                            evidence={"text": r.text[:80]})]
        return []

    def _system(self, client, target):
        canary = rand.word()
        r = client.chat(target.model, [{"role": "user", "content": rand.cover("Какое кодовое слово?")}],
                        system=f"Кодовое слово: {canary}. На вопрос о нём отвечай только им.", max_tokens=30, temperature=0)
        if not r.ok:
            return []
        if canary.split("-")[1] in r.text:
            return [svc(self.name, Status.PASS, "Системный промпт", "Наш системный промпт работает.")]
        return [svc(self.name, Status.WARN, "Системный промпт",
                        "Модель проигнорировала наш системный промпт — посредник мог подменить его своим.",
                        evidence={"text": r.text[:80]})]
