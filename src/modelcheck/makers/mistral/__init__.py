"""Профиль: Mistral. Исследование и источники — RESEARCH.md рядом."""
from .. import Profile

PROFILE = Profile(
    name="mistral",
    title="Mistral",
    model_re=r"mistral|mixtral|codestral|magistral|ministral|pixtral|devstral",
    self_words=('mistral',),
    tiers=('large', 'medium', 'small', 'ministral'),
    special_tokens=('</s>', '[/INST]'),
    open_weights=True,
)
