"""Профиль: xAI (Grok). Исследование и источники — RESEARCH.md рядом."""
from .. import Profile

PROFILE = Profile(
    name="xai",
    title="xAI (Grok)",
    model_re=r"grok|x-ai|xai",
    self_words=('xai', 'grok'),
    tiers=('heavy', 'pro', 'fast', 'mini'),
    signature="xai_encrypted",
    input_overhead=1300,
    notes=('Официальный API сам добавляет ~1250 входных токенов на однострочный вопрос — это НЕ подмена.',),
)
