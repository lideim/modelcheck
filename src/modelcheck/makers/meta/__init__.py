"""Профиль: Meta (Llama). Исследование и источники — RESEARCH.md рядом."""
from .. import Profile

PROFILE = Profile(
    name="meta",
    title="Meta (Llama)",
    model_re=r"llama|meta-llama|(?<![a-z])meta(?![a-z])",
    self_words=('meta', 'llama'),
    tiers=('maverick', 'scout', '70b', '8b'),
    special_tokens=('<|eot_id|>', '<|end_of_text|>', '<|start_header_id|>'),
    open_weights=True,
)
