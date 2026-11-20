"""Профиль: Amazon (Nova). Исследование и источники — RESEARCH.md рядом."""
from .. import Profile

PROFILE = Profile(
    name="amazon",
    title="Amazon (Nova)",
    model_re=r"(?<![a-z])nova-|amazon",
    self_words=('amazon', 'nova', 'kiro', 'amazon q'),
)
