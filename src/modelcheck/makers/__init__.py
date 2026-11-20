"""Профили производителей. Каждый — в своей папке: __init__.py (PROFILE) + RESEARCH.md (как проверять, источники).

Профиль описывает «почерк» производителя: как модель себя называет, какие служебные
токены у её токенизатора, какие поля она отдаёт, есть ли криптоподпись размышлений,
сколько скрытых токенов добавляет сам официальный API.
"""
from __future__ import annotations

import importlib
import pkgutil
import re
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Profile:
    name: str                              # id: anthropic, openai, …
    title: str                             # для отчёта
    model_re: str                          # как узнать по имени модели
    self_words: tuple[str, ...]            # как модель/компания называется в ответах
    native_protocol: str = "openai"        # anthropic | openai | gemini
    tiers: tuple[str, ...] = ()            # дорогой -> дешёвый
    signature: str | None = None           # anthropic_thinking | openai_encrypted | gemini_thought | xai_encrypted
    reasoning_field: str | None = None     # поле с размышлениями в chat completions (reasoning_content)
    special_tokens: tuple[str, ...] = ()   # служебные токены токенизатора
    id_prefixes: tuple[str, ...] = ()      # префиксы id на родном протоколе
    input_overhead: int = 40               # сколько входных токенов на «x» даёт ОФИЦИАЛЬНЫЙ API
    cjk_native: bool = False               # учится на китайском: иероглифы не улика
    open_weights: bool = False             # открытые веса (можно поднять у себя → частая подмена)
    notes: tuple[str, ...] = field(default_factory=tuple)


PROFILES: dict[str, Profile] = {}

for _m in pkgutil.iter_modules(__path__):
    if _m.ispkg:
        _p = importlib.import_module(f"{__name__}.{_m.name}").PROFILE
        PROFILES[_p.name] = _p

# порядок важен: более специфичные шаблоны раньше (gemma — google, а не meta)
_ORDER = sorted(PROFILES.values(), key=lambda p: -len(p.model_re))

UNKNOWN = Profile("unknown", "Неизвестный производитель", r"$^", ())


def maker_of(model: str) -> str:
    m = model.lower()
    for p in _ORDER:
        if re.search(p.model_re, m):
            return p.name
    return "unknown"


def profile(name: str) -> Profile:
    return PROFILES.get(name, UNKNOWN)


def named_makers(text: str) -> set[str]:
    t = text.lower()
    return {p.name for p in PROFILES.values()
            if any(re.search(rf"(?<!\w){re.escape(w)}(?!\w)", t) for w in p.self_words)}


def tier_of(model: str, maker: str) -> str | None:
    m = model.lower()
    for t in profile(maker).tiers:
        if re.search(rf"(?<![a-z]){t}(?![a-z])", m):
            return t
    return None
