"""Профиль: Google (Gemini, Gemma). Исследование и источники — RESEARCH.md рядом."""
from .. import Profile

PROFILE = Profile(
    name="google",
    title="Google (Gemini, Gemma)",
    model_re=r"gemini|gemma|google|palm",
    self_words=('google', 'gemini', 'deepmind', 'gemma'),
    native_protocol="gemini",
    tiers=('ultra', 'pro', 'argon', 'carbon', 'flash', 'lite'),
    signature="gemini_thought",
    input_overhead=40,
    notes=('Gemini 3+ думает по умолчанию: отсутствие следов thinking — признак переходника.',),
)
