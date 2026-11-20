"""Профиль: ByteDance (Doubao, Seed). Исследование и источники — RESEARCH.md рядом."""
from .. import Profile

PROFILE = Profile(
    name="bytedance",
    title="ByteDance (Doubao, Seed)",
    model_re=r"doubao|seed-|bytedance|volc",
    self_words=('bytedance', 'doubao', '豆包', '字节'),
    tiers=('pro', 'turbo', 'lite'),
    reasoning_field="reasoning_content",
    cjk_native=True,
)
