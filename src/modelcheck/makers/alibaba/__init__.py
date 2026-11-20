"""Профиль: Alibaba (Qwen). Исследование и источники — RESEARCH.md рядом."""
from .. import Profile

PROFILE = Profile(
    name="alibaba",
    title="Alibaba (Qwen)",
    model_re=r"qwen|qwq|alibaba|tongyi|dashscope",
    self_words=('alibaba', 'qwen', 'tongyi', '通义'),
    tiers=('max', 'plus', 'turbo', 'flash'),
    reasoning_field="reasoning_content",
    special_tokens=('<|im_end|>', '<|endoftext|>'),
    cjk_native=True,
    open_weights=True,
)
