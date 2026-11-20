"""Скрытый системный промпт и честность параметров.

1. Скрытый промпт: отправляем сообщение из одного символа. Честный API
   насчитает ~5–20 входных токенов. Если сотни/тысячи — посредник вшивает
   свой системный промпт (часто «You are Claude…» поверх другой модели),
   и вы ещё платите за эти токены.
2. max_tokens: просим ответ не длиннее 5 токенов. Если вернулось больше —
   параметры не доходят до модели (переписываются посредником).
"""
from __future__ import annotations

from ...core.check import Check, register
from ...core.types import Finding, Status, svc
from ...makers import profile


@register
class HiddenPrompt(Check):
    name = "hidden_prompt"
    title = "Скрытый системный промпт"
    level = 1

    def run(self, client, target, maker):
        out = []
        normal_max = profile(maker).input_overhead   # у Grok официальный API сам добавляет ~1250
        r = client.chat(target.model, [{"role": "user", "content": "x"}], max_tokens=5)
        if not r.ok:
            return [svc(self.name, Status.SKIP, self.title, f"Нет ответа: {r.error}")]
        u = r.usage
        inp = u.get("input_tokens", u.get("prompt_tokens"))
        cache = sum(v for k, v in u.items() if "cache_creation" in k and isinstance(v, int))
        cache += u.get("cache_read_input_tokens", 0) or 0
        total_in = (inp or 0) + (cache if "input_tokens" in u else 0)
        if inp is None:
            out.append(svc(self.name, Status.WARN, self.title, "Сервер не сообщает число входных токенов."))
        elif total_in > normal_max:
            out.append(svc(self.name, Status.FAIL, self.title,
                               f"На сообщение из 1 символа насчитано {total_in} входных токенов "
                               f"(у официального API {maker} норма до ~{normal_max}). "
                               "Посредник подмешивает свой скрытый промпт — и списывает за него с вас.",
                               evidence={"usage": u}))
        else:
            out.append(svc(self.name, Status.PASS, self.title, f"Входных токенов {total_in} — лишнего не подмешано."))

        outp = u.get("output_tokens", u.get("completion_tokens"))
        if outp is not None:
            if outp > 5 + 2:
                out.append(svc(self.name, Status.WARN, "Параметр max_tokens",
                                   f"Просили не больше 5 токенов, получили {outp}: параметры запроса не доходят до модели."))
            else:
                out.append(svc(self.name, Status.PASS, "Параметр max_tokens", "Ограничение длины соблюдено."))
        return out
