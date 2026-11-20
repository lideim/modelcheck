"""Профиль: Anthropic (Claude). Исследование и источники — RESEARCH.md рядом."""
from .. import Profile

PROFILE = Profile(
    name="anthropic",
    title="Anthropic (Claude)",
    model_re=r"claude|anthropic",
    self_words=('anthropic', 'claude'),
    native_protocol="anthropic",
    tiers=('opus', 'sonnet', 'haiku'),
    signature="anthropic_thinking",
    id_prefixes=('msg_',),
    input_overhead=40,
    notes=('Самая сильная проверка в мире: подпись блока thinking, подделать нельзя.',),
)
