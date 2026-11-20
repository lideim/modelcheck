"""Форма ответа: id, usage, чужие поля.

У каждого производителя свой «почерк» ответа:
- Anthropic: id начинается с msg_, usage с input_tokens/output_tokens;
- OpenAI: id chatcmpl-…, system_fingerprint fp_…;
- DeepSeek выдаёт себя полем reasoning_content (у Claude/GPT его нет).
Чужие поля в ответе — след того, что внутри другая модель или переходник.
"""
from __future__ import annotations

from ...core.check import Check, register
from ...core.types import Finding, Status
from ...makers import PROFILES, profile

ID_PREFIX = {"anthropic": ("msg_",), "openai": ("chatcmpl-", "resp_")}
# у кого родное поле reasoning_content (DeepSeek и китайские открытые модели)
REASONING_FIELD_MAKERS = {n for n, p in PROFILES.items() if p.reasoning_field == "reasoning_content"}


@register
class ResponseShape(Check):
    name = "response_shape"
    title = "Форма ответа (id, usage, чужие поля)"
    level = 1

    def run(self, client, target, maker):
        r = client.chat(target.model, [{"role": "user", "content": "Привет! Ответь одним словом."}], max_tokens=30)
        if not r.ok:
            return [Finding(self.name, Status.SKIP, self.title, f"Нет ответа: {r.error}")]
        out = []

        # 1. reasoning_content у тех, у кого его быть не должно
        if r.extra.get("reasoning_content") and maker not in REASONING_FIELD_MAKERS:
            out.append(Finding(self.name, Status.FAIL, "Поле reasoning_content",
                               "В ответе есть reasoning_content — фирменное поле DeepSeek и китайских моделей "
                               f"({', '.join(sorted(REASONING_FIELD_MAKERS))}). У {maker} его быть не должно.", critical=True))

        # 1б. размышления в тексте <think>…</think> — так отвечают открытые модели (DeepSeek-R1, Qwen, MiniMax)
        if "<think>" in r.text and not profile(maker).open_weights:
            out.append(Finding(self.name, Status.FAIL, "Теги <think>",
                               f"В тексте ответа теги <think> — почерк открытых reasoning-моделей, не {maker}.",
                               critical=True, evidence={"text": r.text[:80]}))

        # 2. префикс id (только если протокол родной для производителя)
        prefixes = profile(maker).id_prefixes
        native = profile(maker).native_protocol == target.protocol and prefixes
        if native and r.id:
            if r.id.startswith(prefixes):
                out.append(Finding(self.name, Status.PASS, "Префикс id", f"id «{r.id[:12]}…» в родном формате."))
            else:
                out.append(Finding(self.name, Status.WARN, "Префикс id",
                                   f"id «{r.id[:16]}» не похож на родной ({' / '.join(prefixes)})."))
        elif native and not r.id:
            out.append(Finding(self.name, Status.WARN, "Префикс id", "В ответе нет id."))

        # 3. usage: чужая схема полей
        u = r.usage
        if not u:
            out.append(Finding(self.name, Status.WARN, "Учёт токенов", "Поле usage пустое — нельзя проверить, за что списывают."))
        else:
            anth_style = "input_tokens" in u or "cache_creation_input_tokens" in u
            oai_style = "prompt_tokens" in u
            if target.protocol == "openai" and maker != "anthropic" and any("cache_creation" in k for k in u):
                out.append(Finding(self.name, Status.FAIL, "Учёт токенов",
                                   "В usage следы Anthropic (cache_creation_*), хотя модель не Claude: внутри другой бэкенд.",
                                   critical=True))
            elif target.protocol == "anthropic" and oai_style and not anth_style:
                out.append(Finding(self.name, Status.WARN, "Учёт токенов",
                                   "usage в формате OpenAI на Anthropic-протоколе: стоит переходник."))
            else:
                out.append(Finding(self.name, Status.PASS, "Учёт токенов", "Схема usage соответствует протоколу."))

        # 4. system_fingerprint у OpenAI
        if target.protocol == "openai" and maker == "openai":
            fp = r.extra.get("system_fingerprint")
            if fp and str(fp).startswith("fp_"):
                out.append(Finding(self.name, Status.PASS, "system_fingerprint", f"Есть, формат OpenAI ({fp})."))
            else:
                out.append(Finding(self.name, Status.INFO, "system_fingerprint",
                                   "Нет поля fp_…: у новых моделей OpenAI бывает, но настораживает в сумме."))

        # 5. посредник в заголовках — факт, не обвинение
        h = {k.lower(): v for k, v in r.headers.items()}
        hops = [k for k in ("via", "x-oneapi-request-id", "x-new-api-version") if k in h]
        if hops:
            out.append(Finding(self.name, Status.INFO, "Посредник",
                               f"Ответ прошёл через прокси/перепродавца (заголовки: {', '.join(hops)}). "
                               "Это не доказательство подмены.", evidence={"headers": hops}))
        return out
