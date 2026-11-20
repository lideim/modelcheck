"""Профиль: OpenAI (GPT). Исследование и источники — RESEARCH.md рядом."""
from .. import Profile

PROFILE = Profile(
    name="openai",
    title="OpenAI (GPT)",
    model_re=r"(?<![a-z])gpt|openai|chatgpt|(?<![a-z])o[1-9](?![a-z0-9])",
    self_words=('openai', 'chatgpt', 'gpt'),
    tiers=('astra', 'sol', 'terra', 'luna', 'mini', 'nano'),
    signature="openai_encrypted",
    id_prefixes=('chatcmpl-', 'resp_'),
    input_overhead=40,
    notes=('Криптоподписи как у Claude нет: encrypted_content проверяется только через Responses API.',),
)
