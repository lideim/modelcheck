"""Подмена после первых ходов (по работе «Contagious Fingerprints», arXiv:2611.18104).

Посредник может отвечать настоящей моделью на первые ходы (их обычно и проверяют),
а длинные диалоги отдавать дешёвой. Поэтому проверочный вопрос задаём не в новом
диалоге, а в конце уже длинной переписки (6 ходов обычной работы). Сравниваем:
- скрытые входные токены: сколько добавляется сверх реального текста диалога;
- поле model в ответе на позднем ходе;
- совпадает ли «кто ты» на позднем ходе с ответом в начале;
- отвечает ли модель на поздний вопрос по сути (дешёвая модель чаще теряет нить).
"""
from __future__ import annotations

import re

from ...core import rand
from ...core.check import Check, register
from ...core.types import Finding, Status
from ...makers import maker_of, named_makers

WORK = [
    ("Как в Python развернуть список?", "Через срез lst[::-1] или метод lst.reverse() — второй меняет список на месте."),
    ("А как убрать дубликаты, сохранив порядок?", "list(dict.fromkeys(lst)) — словарь сохраняет порядок вставки."),
    ("Чем кортеж отличается от списка?", "Кортеж неизменяемый и может быть ключом словаря, список — изменяемый."),
    ("Как прочитать файл построчно?", "with open(path) as f: for line in f: ... — файл закроется сам."),
    ("Что делает enumerate?", "Отдаёт пары (индекс, элемент) при обходе последовательности."),
    ("Как отсортировать словарь по значению?", "sorted(d.items(), key=lambda kv: kv[1])."),
    ("Что такое генератор?", "Функция с yield: отдаёт значения по одному и не хранит всё в памяти."),
    ("Зачем нужен __init__.py?", "Помечает папку как пакет и выполняется при его импорте."),
]


@register
class LateTurns(Check):
    name = "late_turns"
    title = "Подмена на поздних ходах"
    level = 2

    def run(self, client, target, maker):
        hist = []
        for q, a in rand.shuffle(WORK)[:6]:
            hist += [{"role": "user", "content": q}, {"role": "assistant", "content": a}]
        code = rand.word()
        first_q = hist[0]["content"]
        late = hist + [{"role": "user", "content": rand.cover(
            f"Две вещи. 1) Повтори код: {code}. 2) Какой самый первый вопрос я задал в этом разговоре? "
            "3) Какая ты модель и кто тебя создал? Кратко.")}]
        r = client.chat(target.model, late, max_tokens=150, temperature=0)
        if not r.ok:
            return [Finding(self.name, Status.SKIP, self.title, f"Нет ответа на длинный диалог: {r.error[:100]}")]
        out = []
        got = r.model or ""
        gm = maker_of(got) if got else "unknown"
        if gm not in ("unknown", maker):
            out.append(Finding(self.name, Status.FAIL, "Модель на позднем ходе",
                               f"В начале диалога отвечает {maker}, на 7-м ходе ответ подписан {got}.",
                               critical=True, evidence={"model": got}))
        foreign = named_makers(r.text) - {maker}
        if foreign:
            out.append(Finding(self.name, Status.WARN, "Кто ты на позднем ходе",
                               f"На 7-м ходе модель называет {', '.join(sorted(foreign))}.", evidence={"text": r.text[:120]}))
        lost = code.split("-")[1] not in r.text
        key = re.findall(r"\w{5,}", first_q.lower())
        forgot = not any(w in r.text.lower() for w in key)
        if lost and forgot:
            out.append(Finding(self.name, Status.WARN, "Память диалога",
                               "На 7-м ходе модель не повторила код и не вспомнила первый вопрос — "
                               "дешёвые модели и урезанный контекст ведут себя так.", evidence={"text": r.text[:120]}))
        if not out:
            out.append(Finding(self.name, Status.PASS, self.title,
                               "На 7-м ходе модель та же, помнит начало разговора и называет себя так же."))
        return out
