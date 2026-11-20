"""Профиль: DeepSeek. Исследование и источники — RESEARCH.md рядом."""
from .. import Profile

PROFILE = Profile(
    name="deepseek",
    title="DeepSeek",
    model_re=r"deepseek",
    self_words=('deepseek',),
    tiers=('reasoner', 'pro', 'chat', 'flash'),
    reasoning_field="reasoning_content",
    special_tokens=('<｜end▁of▁sentence｜>', '<｜begin▁of▁sentence｜>'),
    cjk_native=True,
    open_weights=True,
)
