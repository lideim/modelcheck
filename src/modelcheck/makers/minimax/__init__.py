"""Профиль: MiniMax. Исследование и источники — RESEARCH.md рядом."""
from .. import Profile

PROFILE = Profile(
    name="minimax",
    title="MiniMax",
    model_re=r"minimax|abab",
    self_words=('minimax',),
    reasoning_field="reasoning_content",
    cjk_native=True,
    open_weights=True,
)
