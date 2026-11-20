"""Профиль: Zhipu (GLM). Исследование и источники — RESEARCH.md рядом."""
from .. import Profile

PROFILE = Profile(
    name="zhipu",
    title="Zhipu (GLM)",
    model_re=r"glm|zhipu|z-ai|chatglm|bigmodel",
    self_words=('zhipu', 'glm', 'chatglm', '智谱'),
    tiers=('plus', 'air', 'flash'),
    reasoning_field="reasoning_content",
    special_tokens=('<|user|>', '<|endoftext|>'),
    cjk_native=True,
    open_weights=True,
)
