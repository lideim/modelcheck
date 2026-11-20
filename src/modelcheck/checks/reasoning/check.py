"""Размышления у reasoning-моделей всех производителей (кроме подписи Claude — она отдельно).

Что проверяем, в зависимости от профиля производителя:
- OpenAI / xAI: Responses API с include=["reasoning.encrypted_content"] должен вернуть
  зашифрованный блок размышлений, и сервер должен принять его обратно следующим ходом.
  Подделать шифр нельзя → сильная улика (★★☆, у посредника Responses API может не быть).
- DeepSeek / Qwen / GLM / Kimi / Doubao / MiniMax: reasoning-версия должна отдавать поле
  reasoning_content. Нет поля у «reasoner» → подсунули обычную chat-модель (кейс CISPA:
  deepseek-chat вместо deepseek-reasoner).
- Все: usage.completion_tokens_details.reasoning_tokens. На задаче, где нужно подумать,
  у reasoning-модели > 0. Ноль → вырезали размышления или отдали другую модель.
"""
from __future__ import annotations

import re

from ...core import rand
from ...core.check import Check, register
from ...core.types import Finding, Status
from ...makers import profile

NAMES = ["Аня", "Маша", "Оля", "Катя", "Лена", "Вика"]
REASONING_NAME = re.compile(r"reason|think|(?<![a-z])r1(?![0-9])|(?<![a-z])o[1-9](?![a-z0-9])|-pro|qwq|magistral|k3|thinking")


def make_task() -> tuple[str, str]:
    """Задача с подвохом: у девочки N братьев, у каждого брата S сестёр → сестёр у неё S-1."""
    name, n, s = rand.pick(NAMES), rand.number(2, 4), rand.number(2, 4)
    q = (f"У {name[:-1]}и {n} брата, у каждого брата {s} сестры. "
         f"Сколько сестёр у {name[:-1]}и? Ответь только числом.")
    return rand.cover(q), str(s - 1)


@register
class Reasoning(Check):
    name = "reasoning"
    title = "Размышления reasoning-моделей"
    protocols = ("openai",)
    level = 2

    def applies(self, target, maker):
        p = profile(maker)
        return target.protocol == "openai" and (p.signature in ("openai_encrypted", "xai_encrypted") or p.reasoning_field)

    def run(self, client, target, maker):
        p = profile(maker)
        out = []
        is_reasoning = bool(REASONING_NAME.search(target.model.lower()))
        task, answer = make_task()

        # 1. зашифрованные размышления OpenAI / xAI
        if p.signature in ("openai_encrypted", "xai_encrypted"):
            r = client.responses(target.model, task, include_encrypted=True)
            if r.status == 404 or (not r.ok and "responses" in r.error.lower()):
                out.append(Finding(self.name, Status.INFO, "Зашифрованные размышления",
                                   "Responses API недоступен у посредника — проверить шифр размышлений нельзя."))
            elif not r.ok:
                out.append(Finding(self.name, Status.INFO, "Зашифрованные размышления", f"Запрос не прошёл: {r.error[:120]}"))
            else:
                enc = r.extra.get("encrypted_reasoning")
                if not enc:
                    out.append(Finding(self.name, Status.WARN if is_reasoning else Status.INFO, "Зашифрованные размышления",
                                       "Responses API ответил, но без encrypted_content."))
                else:
                    back = client.responses(target.model, "А если братьев на одного больше?", include_encrypted=True,
                                            previous_items=r.extra["output_items"])
                    if back.ok:
                        out.append(Finding(self.name, Status.PASS, "Зашифрованные размышления",
                                           f"Шифр размышлений есть ({len(enc)} симв.) и принят сервером обратно."))
                    elif "encrypt" in back.error.lower() or "reasoning" in back.error.lower():
                        out.append(Finding(self.name, Status.FAIL, "Зашифрованные размышления",
                                           f"Сервер отклонил собственный шифр: {back.error[:140]}", critical=True))
                    else:
                        out.append(Finding(self.name, Status.WARN, "Зашифрованные размышления",
                                           f"Шифр есть, но повторная отправка упала: {back.error[:120]}"))

        # 2. reasoning_content у китайских reasoning-моделей + reasoning_tokens у всех
        r = client.chat(target.model, [{"role": "user", "content": task}], max_tokens=2000)
        if not r.ok:
            out.append(Finding(self.name, Status.SKIP, "Счётчик размышлений", f"Нет ответа: {r.error[:120]}"))
            return out
        rt = ((r.usage.get("completion_tokens_details") or {}).get("reasoning_tokens"))
        has_field = bool(r.extra.get("reasoning_content") or r.extra.get("reasoning"))
        if p.reasoning_field and is_reasoning:
            if has_field or (rt or 0) > 0:
                out.append(Finding(self.name, Status.PASS, "Поле размышлений",
                                   f"Reasoning-модель отдала размышления ({'reasoning_content' if has_field else f'{rt} токенов'})."))
            else:
                out.append(Finding(self.name, Status.FAIL, "Поле размышлений",
                                   f"Заявлена reasoning-модель, но нет ни {p.reasoning_field}, ни reasoning_tokens: "
                                   "похоже, отдают обычную chat-версию (так подменяли deepseek-reasoner на deepseek-chat).",
                                   critical=True))
        elif rt is not None:
            if is_reasoning and rt == 0:
                out.append(Finding(self.name, Status.WARN, "Счётчик размышлений",
                                   "reasoning_tokens = 0 на задаче с подвохом: размышления вырезаны или модель не reasoning."))
            else:
                out.append(Finding(self.name, Status.INFO, "Счётчик размышлений", f"reasoning_tokens = {rt}."))
        # правильный ответ — S-1 (сама девочка тоже сестра); невнимательные модели отвечают S
        m = re.search(r"\d+", r.text)
        if m and m.group() != answer and is_reasoning:
            out.append(Finding(self.name, Status.WARN, "Задача на внимательность",
                               f"Ответ {m.group()} вместо {answer}: reasoning-модель уровня заявленной решает такое без ошибок."))
        return out
