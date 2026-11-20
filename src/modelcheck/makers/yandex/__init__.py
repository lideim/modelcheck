"""Профиль: Яндекс (YandexGPT, Алиса). Исследование и источники — RESEARCH.md рядом."""
from .. import Profile

PROFILE = Profile(
    name="yandex",
    title="Яндекс (YandexGPT, Алиса)",
    model_re=r"yandex|yandexgpt|alice|алиса",
    self_words=('yandex', 'яндекс', 'yandexgpt', 'алиса'),
    tiers=('pro', 'lite'),
)
