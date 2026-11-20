"""Профиль: Сбер (GigaChat). Исследование и источники — RESEARCH.md рядом."""
from .. import Profile

PROFILE = Profile(
    name="sber",
    title="Сбер (GigaChat)",
    model_re=r"gigachat|sber",
    self_words=('gigachat', 'гигачат', 'сбер', 'sber'),
    tiers=('max', 'pro', 'lite'),
)
