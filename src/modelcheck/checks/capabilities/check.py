"""Возможности: вызов инструментов и длинный контекст.

Перепродавцы часто урезают то, что дорого: вырезают tools, режут контекст
(заявлен 200k — реально 8k) или отдают меньшую модель, которая не тянет.
- tools: даём функцию get_weather и ждём корректный вызов с городом;
- «иголка в стоге сена»: прячем код в начало длинного текста и спрашиваем в конце.
"""
from __future__ import annotations

import random

from ...core.check import Check, register
from ...core.types import Finding, Status, svc

TOOL = {"name": "get_weather", "description": "Погода в городе",
        "input_schema": {"type": "object", "properties": {"city": {"type": "string"}}, "required": ["city"]}}
FILLER = ("Сервер принимает запросы, пишет логи и отвечает клиентам. "
          "Администратор проверяет нагрузку и обновляет пакеты. ")


@register
class ToolUse(Check):
    name = "capabilities"
    title = "Инструменты (tool use)"
    level = 2

    def run(self, client, target, maker):
        r = client.chat(target.model, [{"role": "user", "content": "Какая сейчас погода в Барнауле? Используй инструмент."}],
                        tools=[TOOL], max_tokens=200)
        if not r.ok:
            return [svc(self.name, Status.WARN, self.title, f"Запрос с tools отклонён: {r.error[:120]}")]
        if not r.tool_calls:
            return [svc(self.name, Status.WARN, self.title, "Модель не вызвала инструмент — tools могли вырезать.")]
        call = r.tool_calls[0]
        args = call.get("input") or call.get("function", {}).get("arguments", "")
        if "арнаул" in str(args) or "arnaul" in str(args).lower():
            return [svc(self.name, Status.PASS, self.title, "Инструмент вызван корректно.")]
        return [svc(self.name, Status.WARN, self.title, f"Вызов есть, но аргументы странные: {str(args)[:80]}")]


@register
class LongContext(Check):
    name = "long_context"
    title = "Длинный контекст (иголка в стоге)"
    level = 3

    def __init__(self, tokens: int = 30000):
        self.tokens = tokens

    def run(self, client, target, maker):
        code = f"ИГЛА-{random.randint(10000, 99999)}"
        reps = self.tokens * 3 // len(FILLER)          # ~3 символа на токен для русского
        text = f"Секретный код: {code}.\n\n" + FILLER * reps
        r = client.chat(target.model, [{"role": "user", "content": text + "\n\nКакой секретный код был в самом начале? Только код."}],
                        max_tokens=30)
        if not r.ok:
            return [svc(self.name, Status.WARN, self.title,
                            f"Текст ~{self.tokens // 1000}k токенов не принят: {r.error[:120]}")]
        used = r.usage.get("input_tokens", r.usage.get("prompt_tokens"))
        if code.split("-")[1] in r.text:
            return [svc(self.name, Status.PASS, self.title, f"Нашла код в начале ~{(used or self.tokens) // 1000}k токенов.")]
        return [svc(self.name, Status.FAIL, self.title,
                        f"Не нашла код из начала (~{(used or self.tokens) // 1000}k токенов): контекст обрезают.",
                        evidence={"answer": r.text[:60], "input_tokens": used})]
