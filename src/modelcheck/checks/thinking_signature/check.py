"""Подпись размышлений Claude — криптографическая, подделать нельзя.

Как работает: просим модель «подумать» (extended thinking). Настоящий Claude
возвращает блок thinking с полем signature (~500–2000 символов), подписанным
серверами Anthropic. Затем отдаём этот блок обратно во втором ходе: настоящий
API примет подпись, а подделанную отклонит с ошибкой 400.
"""
from __future__ import annotations

from ...core import rand
from ...core.check import Check, register
from ...core.types import Finding, Status


@register
class ThinkingSignature(Check):
    name = "thinking_signature"
    title = "Подпись размышлений Claude"
    protocols = ("anthropic",)
    makers = ("anthropic",)
    level = 1

    def run(self, client, target, maker):
        a, b = rand.number(12, 49), rand.number(12, 49)
        msgs = [{"role": "user", "content": rand.cover(f"Сколько будет {a} * {b}? Ответь одним числом.")}]
        r = client.chat(target.model, msgs, max_tokens=2000, thinking=1024)
        if not r.ok:
            return [Finding(self.name, Status.SKIP, self.title, f"Запрос с thinking не прошёл: {r.error}")]

        signed = [b for b in r.thinking if b.get("type") == "thinking" and b.get("signature")]
        redacted = [b for b in r.thinking if b.get("type") == "redacted_thinking"]
        think_tokens = (r.usage.get("output_tokens_details") or {}).get("thinking_tokens")

        if not r.thinking:
            return [Finding(
                self.name, Status.WARN, self.title,
                "Режим размышлений запрошен, но блок thinking не вернулся"
                + (f" (thinking_tokens = {think_tokens})" if think_tokens is not None else "")
                + ". Посредник вырезает этот режим или за ним не Claude. Главный способ проверки недоступен.",
                evidence={"thinking_tokens": think_tokens})]

        if redacted and not signed:
            return [Finding(self.name, Status.PASS, self.title,
                            "Пришёл зашифрованный блок redacted_thinking: такое отдаёт только Anthropic.")]

        sig = signed[0]["signature"]
        if len(sig) < 200:
            return [Finding(self.name, Status.FAIL, self.title,
                            f"Подпись подозрительно короткая ({len(sig)} симв.), у настоящей 500–2000+.",
                            critical=True, evidence={"len": len(sig)})]

        # второй ход: возвращаем подписанный блок — подделку API отклонит
        follow = msgs + [{"role": "assistant", "content": r.raw["content"]},
                         {"role": "user", "content": f"А {a} * {b + 1}?"}]
        r2 = client.chat(target.model, follow, max_tokens=2000, thinking=1024)
        if r2.ok:
            return [Finding(self.name, Status.PASS, self.title,
                            f"Подпись есть ({len(sig)} симв.) и принята сервером при повторной отправке.",
                            evidence={"len": len(sig)})]
        low = r2.error.lower()
        if "signature" in low or "thinking" in low or "cannot be modified" in low:
            return [Finding(self.name, Status.FAIL, self.title,
                            f"Сервер отклонил собственную подпись: {r2.error[:160]}. Подпись поддельная.",
                            critical=True)]
        return [Finding(self.name, Status.WARN, self.title,
                        f"Подпись есть ({len(sig)} симв.), но повторная отправка упала: {r2.error[:120]}")]
