"""Профиль: NVIDIA (Nemotron). Исследование и источники — RESEARCH.md рядом."""
from .. import Profile

PROFILE = Profile(
    name="nvidia",
    title="NVIDIA (Nemotron)",
    model_re=r"nemotron|nvidia",
    self_words=('nvidia', 'nemotron'),
    open_weights=True,
)
