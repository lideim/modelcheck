"""Профиль: Microsoft (Phi, MAI). Исследование и источники — RESEARCH.md рядом."""
from .. import Profile

PROFILE = Profile(
    name="microsoft",
    title="Microsoft (Phi, MAI)",
    model_re=r"(?<![a-z])phi-|microsoft|mai-",
    self_words=('microsoft', 'phi'),
    special_tokens=('<|end|>', '<|endoftext|>'),
    open_weights=True,
)
