"""Профиль: Cohere (Command). Исследование и источники — RESEARCH.md рядом."""
from .. import Profile

PROFILE = Profile(
    name="cohere",
    title="Cohere (Command)",
    model_re=r"cohere|command-[ar]",
    self_words=('cohere',),
)
