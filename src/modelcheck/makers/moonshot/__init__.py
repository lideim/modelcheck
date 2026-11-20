"""Профиль: Moonshot (Kimi). Исследование и источники — RESEARCH.md рядом."""
from .. import Profile

PROFILE = Profile(
    name="moonshot",
    title="Moonshot (Kimi)",
    model_re=r"kimi|moonshot",
    self_words=('moonshot', 'kimi', '月之暗面'),
    tiers=('pro', 'turbo'),
    reasoning_field="reasoning_content",
    special_tokens=('<|im_end|>',),
    cjk_native=True,
    open_weights=True,
)
