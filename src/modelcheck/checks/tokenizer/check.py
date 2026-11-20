"""Отпечаток токенизатора: сколько input-токенов насчитали за один и тот же текст.

Каждое семейство моделей режет текст на токены по-своему. Системный промпт
может заставить модель назвать себя кем угодно, но токенизатор не изменит.
Шлём тексты разных алфавитов и сравниваем число токенов с эталонами, снятыми
с заведомо настоящих ключей (команда baseline).
"""
from __future__ import annotations

from ...core import baselines
from ...core.check import Check, register
from ...core.types import Finding, Status

SAMPLES = {
    "en": "The quick brown fox jumps over the lazy dog while the server logs every request.",
    "ru": "Съешь же ещё этих мягких французских булок да выпей чаю, пока сервер пишет логи.",
    "zh": "敏捷的棕色狐狸跳过了懒狗，服务器记录了每一个请求。",
    "code": "def f(x: int) -> list[str]:\n    return [str(i ** 2) for i in range(x) if i % 3 == 0]",
}


def measure(client, model, tries: int = 2) -> dict[str, int] | None:
    """Токены каждого текста = input_tokens(«x» + текст) − input_tokens(«x»).

    Замер дважды: если разница «плавает» (кэш, скрытый промпт меняется) — данным
    не доверяем. Проверка здравого смысла: токенов не больше, чем символов.
    """
    def inp(text: str) -> int | None:
        r = client.chat(model, [{"role": "user", "content": text}], max_tokens=1)
        if not r.ok:
            return None
        u = r.usage
        return u.get("input_tokens", u.get("prompt_tokens"))

    out = {}
    for k, t in SAMPLES.items():
        vals = []
        for _ in range(tries):
            a, b = inp("x"), inp("x " + t)
            if a is None or b is None:
                return None
            vals.append(b - a)
        if max(vals) - min(vals) > 1 or not 0 < vals[0] <= len(t):
            return None
        out[k] = vals[0]
    return out


def distance(a: dict, b: dict) -> float:
    """Средняя относительная разница по всем текстам (0 = совпадение)."""
    keys = [k for k in SAMPLES if k in a and k in b and b[k]]
    return sum(abs(a[k] - b[k]) / b[k] for k in keys) / max(len(keys), 1)


@register
class Tokenizer(Check):
    name = "tokenizer"
    title = "Отпечаток токенизатора"
    level = 2

    def run(self, client, target, maker):
        got = measure(client, target.model)
        if not got:
            return [Finding(self.name, Status.SKIP, self.title,
                            "Счётчик входных токенов отсутствует или «плавает» между одинаковыми запросами — замер ненадёжен.")]
        bases = baselines.load("tokens")
        if not bases:
            return [Finding(self.name, Status.INFO, self.title,
                            f"Замер: {got}. Эталонов нет — сними их командой «modelcheck baseline».",
                            evidence={"tokens": got})]
        ranked = sorted(((distance(got, v["tokens"]), name, v) for name, v in bases.items()), key=lambda x: x[0])
        best_d, best_name, best = ranked[0]
        own_list = [(d, n, v) for d, n, v in ranked if v.get("maker") == maker]
        ev = {"tokens": got, "closest": best_name, "distance": round(best_d, 3)}
        if own_list and own_list[0][0] <= 0.05:
            d, n, v = own_list[0]
            return [Finding(self.name, Status.PASS, self.title,
                            f"Токенизатор совпадает с эталоном {n} (расхождение {d:.0%}){baselines.stale_note(v)}.", evidence=ev)]
        own = own_list[0][0] if own_list else None
        if best.get("maker") != maker and best_d <= 0.05 and (own is None or own > 0.15):
            return [Finding(self.name, Status.FAIL, self.title,
                            f"Текст режется как у {best['maker']} ({best_name}), а не как у {maker}. "
                            f"Подменить токенизатор промптом нельзя{baselines.stale_note(best)}.", critical=True, evidence=ev)]
        if not own_list:
            return [Finding(self.name, Status.INFO, self.title,
                            f"Нет эталона для {maker}. Ближе всего: {best_name} ({best_d:.0%}).", evidence=ev)]
        return [Finding(self.name, Status.WARN, self.title,
                        f"Ни один эталон не совпал точно (до своего {own:.0%}). Возможна другая версия модели"
                        f"{baselines.stale_note(own_list[0][2])}.", evidence=ev)]
