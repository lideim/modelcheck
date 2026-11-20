"""Тесты без сети: поддельный клиент отвечает так, как отвечал бы настоящий или поддельный API."""
from __future__ import annotations

import modelcheck.checks  # noqa: F401
from modelcheck.checks.hidden_prompt.check import HiddenPrompt
from modelcheck.checks.identity.check import Identity
from modelcheck.checks.model_field.check import ModelField
from modelcheck.checks.random_number.check import jsd
from modelcheck.checks.response_shape.check import ResponseShape
from modelcheck.checks.thinking_signature.check import ThinkingSignature
from modelcheck.checks.tokenizer.check import distance
from modelcheck.core.client import Reply
from modelcheck.core.engine import decide
from modelcheck.makers import maker_of, named_makers, tier_of
from modelcheck.core.types import Finding, Status, Target, Verdict
from collections import Counter

T = Target("https://x", "sk-test-1234567890", "anthropic/claude-opus-4.8", "anthropic")


class Fake:
    """Отдаёт заготовленные ответы по очереди (или функцией)."""

    def __init__(self, fn):
        self.fn, self.count = fn, 0

    def chat(self, model, messages, **kw):
        self.count += 1
        return self.fn(model, messages, kw)


def ok(**kw) -> Reply:
    return Reply(status=200, **kw)


# --- makers ---
def test_maker_detection():
    assert maker_of("anthropic/claude-opus-4.8") == "anthropic"
    assert maker_of("openai/gpt-5.5") == "openai"
    assert maker_of("deepseek/deepseek-v4-flash") == "deepseek"
    assert tier_of("claude-haiku-4-5", "anthropic") == "haiku"
    assert named_makers("Я — DeepSeek-R1 от компании DeepSeek") == {"deepseek"}
    assert "yandex" in named_makers("**Яндекс**")


# --- model_field ---
def test_tier_swap_is_caught():
    def fn(model, msgs, kw):
        if "nonexistent" in model:
            return Reply(status=404, error="not found")
        return ok(text="ок", model="claude-haiku-4-5")
    res = ModelField().run(Fake(fn), T, "anthropic")
    assert res[0].status is Status.FAIL and res[0].critical


def test_phantom_model_answered_is_fail():
    res = ModelField().run(Fake(lambda m, ms, kw: ok(text="ok", model="claude-opus-4-8")), T, "anthropic")
    assert res[0].status is Status.PASS
    assert res[1].status is Status.FAIL


# --- thinking ---
def test_no_thinking_block_is_warn():
    f = ThinkingSignature().run(Fake(lambda m, ms, kw: ok(text="391", usage={"output_tokens": 3})), T, "anthropic")
    assert f[0].status is Status.WARN


def test_valid_signature_passes():
    blk = {"type": "thinking", "thinking": "...", "signature": "S" * 800}

    def fn(m, ms, kw):
        return ok(text="391", thinking=[blk], raw={"content": [blk, {"type": "text", "text": "391"}]})
    assert ThinkingSignature().run(Fake(fn), T, "anthropic")[0].status is Status.PASS


def test_rejected_signature_is_critical():
    blk = {"type": "thinking", "thinking": "...", "signature": "S" * 800}
    calls = []

    def fn(m, ms, kw):
        calls.append(1)
        if len(calls) == 1:
            return ok(text="391", thinking=[blk], raw={"content": [blk]})
        return Reply(status=400, error="Invalid signature in thinking block")
    f = ThinkingSignature().run(Fake(fn), T, "anthropic")[0]
    assert f.status is Status.FAIL and f.critical


# --- response shape ---
def test_reasoning_content_on_claude_is_fail():
    t = Target("https://x", "k" * 20, "anthropic/claude-opus-4.8", "openai")
    r = ok(text="hi", id="chatcmpl-1", usage={"prompt_tokens": 5}, extra={"reasoning_content": "думаю"})
    res = ResponseShape().run(Fake(lambda m, ms, kw: r), t, "anthropic")
    assert any(f.status is Status.FAIL and f.critical for f in res)


# --- hidden prompt ---
def test_hidden_prompt_detected():
    r = ok(text="x", usage={"prompt_tokens": 3024, "completion_tokens": 5})
    res = HiddenPrompt().run(Fake(lambda m, ms, kw: r), T, "anthropic")
    assert res[0].status is Status.FAIL


def test_clean_prompt_passes():
    r = ok(text="x", usage={"input_tokens": 8, "output_tokens": 3})
    assert HiddenPrompt().run(Fake(lambda m, ms, kw: r), T, "anthropic")[0].status is Status.PASS


# --- identity ---
def test_identity_mixed_is_warn():
    from helpers import model_stub
    stub = model_stub(who=["Я DeepSeek-R1", "I was trained by Anthropic.", "Яндекс"])
    res = Identity().run(Fake(stub), T, "anthropic")
    assert res[0].status is Status.WARN


# --- math ---
def test_jsd_and_distance():
    a = Counter({"x": 10, "y": 2})
    assert jsd(a, a) < 1e-6
    assert jsd(a, Counter({"z": 10})) > 0.9
    assert distance({"en": 17, "ru": 36}, {"en": 17, "ru": 36}) == 0


# --- verdict ---
def test_verdict_rules():
    p = Finding("a", Status.PASS, "")
    assert decide([p, p])[0] is Verdict.GENUINE
    assert decide([p, Finding("a", Status.FAIL, "", critical=True)])[0] is Verdict.FAKE
    assert decide([p, Finding("a", Status.FAIL, "")])[0] is Verdict.SUSPICIOUS
    assert decide([Finding("a", Status.FAIL, ""), Finding("b", Status.FAIL, "")])[0] is Verdict.FAKE
