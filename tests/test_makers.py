"""Тесты новых частей: профили всех производителей, reasoning, чужие стоп-токены, «сорок вопросов»."""
from __future__ import annotations

from collections import Counter

import pytest

import modelcheck.checks  # noqa: F401
from modelcheck.checks.forty_questions.check import loglik
from modelcheck.checks.hidden_prompt.check import HiddenPrompt
from modelcheck.checks.identity.check import Identity
from modelcheck.checks.reasoning.check import Reasoning
from modelcheck.checks.response_shape.check import ResponseShape
from modelcheck.core.client import Reply
from modelcheck.core.types import Status, Target
from modelcheck.makers import PROFILES, maker_of, profile


class Fake:
    def __init__(self, fn, resp=None):
        self.fn, self.resp, self.count = fn, resp, 0

    def chat(self, model, messages, **kw):
        self.count += 1
        return self.fn(model, messages, kw)

    def responses(self, model, text, **kw):
        return self.resp(model, text, kw) if self.resp else Reply(status=404, error="not found")


def ok(**kw):
    return Reply(status=200, **kw)


@pytest.mark.parametrize("model,maker", [
    ("anthropic/claude-opus-4.8", "anthropic"), ("openai/gpt-5.5", "openai"), ("openai/o3", "openai"),
    ("google/gemini-3.5-flash", "google"), ("google/gemma-4", "google"), ("meta-llama/llama-4-maverick", "meta"),
    ("qwen/qwen3-max", "alibaba"), ("z-ai/glm-5.1", "zhipu"), ("moonshotai/kimi-k3", "moonshot"),
    ("deepseek/deepseek-v4-flash", "deepseek"), ("x-ai/grok-4.7", "xai"), ("mistralai/mistral-large", "mistral"),
    ("doubao-seed-2-1-pro-260628", "bytedance"), ("minimax/minimax-m2", "minimax"), ("yandexgpt-pro", "yandex"),
    ("GigaChat-Max", "sber"), ("microsoft/phi-4", "microsoft"), ("cohere/command-a", "cohere"),
    ("amazon/nova-pro", "amazon"), ("nvidia/nemotron-3-super", "nvidia"),
])
def test_all_makers_detected(model, maker):
    assert maker_of(model) == maker


def test_profiles_complete():
    assert len(PROFILES) >= 18
    for p in PROFILES.values():
        assert p.self_words, p.name


def test_grok_overhead_is_not_fake():
    t = Target("https://x", "k" * 20, "x-ai/grok-4.7", "openai")
    r = ok(text="x", usage={"prompt_tokens": 1247, "completion_tokens": 3})
    assert HiddenPrompt().run(Fake(lambda m, ms, kw: r), t, "xai")[0].status is Status.PASS
    t2 = Target("https://x", "k" * 20, "openai/gpt-5.5", "openai")
    assert HiddenPrompt().run(Fake(lambda m, ms, kw: r), t2, "openai")[0].status is Status.FAIL


def test_foreign_stop_token_caught():
    """«Claude» обрывается на <|eot_id|> → это Llama."""
    from helpers import model_stub
    t = Target("https://x", "k" * 20, "anthropic/claude-opus-4.8", "openai")
    res = Identity().run(Fake(model_stub(stops_on=("<|eot_id|>",))), t, "anthropic")
    stop = [f for f in res if f.title == "Чужие стоп-токены"][0]
    assert stop.status is Status.FAIL and "meta" in stop.evidence["families"]


def test_clean_model_passes_stop_tokens():
    from helpers import model_stub
    t = Target("https://x", "k" * 20, "anthropic/claude-opus-4.8", "openai")
    res = Identity().run(Fake(model_stub()), t, "anthropic")
    assert [f for f in res if f.title == "Чужие стоп-токены"][0].status is Status.PASS
    assert [f for f in res if f.title == "Системный промпт"][0].status is Status.PASS


def test_think_tags_on_claude():
    t = Target("https://x", "k" * 20, "anthropic/claude-opus-4.8", "openai")
    r = ok(text="<think>хм</think>Привет", usage={"prompt_tokens": 8})
    assert any(f.title == "Теги <think>" and f.critical for f in ResponseShape().run(Fake(lambda m, ms, kw: r), t, "anthropic"))


def test_reasoner_without_reasoning_is_fail():
    t = Target("https://x", "k" * 20, "deepseek/deepseek-reasoner", "openai")
    r = ok(text="2", usage={"prompt_tokens": 20, "completion_tokens": 1})
    res = Reasoning().run(Fake(lambda m, ms, kw: r), t, "deepseek")
    assert any(f.status is Status.FAIL and f.critical for f in res)


def test_reasoner_with_field_passes():
    t = Target("https://x", "k" * 20, "deepseek/deepseek-reasoner", "openai")
    r = ok(text="2", extra={"reasoning_content": "Аня тоже сестра…"}, usage={"completion_tokens": 40})
    res = Reasoning().run(Fake(lambda m, ms, kw: r), t, "deepseek")
    assert res[0].status is Status.PASS


def test_openai_encrypted_rejected_is_critical():
    t = Target("https://x", "k" * 20, "openai/o3", "openai")
    calls = []

    def resp(m, text, kw):
        calls.append(1)
        if len(calls) == 1:
            return ok(text="2", extra={"encrypted_reasoning": "E" * 600, "output_items": [{"type": "reasoning"}]})
        return Reply(status=400, error="Invalid encrypted_content for reasoning item")
    res = Reasoning().run(Fake(lambda m, ms, kw: ok(text="2", usage={}), resp), t, "openai")
    assert res[0].status is Status.FAIL and res[0].critical


def test_reasoning_applies_only_where_meaningful():
    t = Target("https://x", "k" * 20, "anthropic/claude-opus-4.8", "anthropic")
    assert not Reasoning().applies(t, "anthropic")
    assert Reasoning().applies(Target("https://x", "k", "openai/o3", "openai"), "openai")
    assert profile("deepseek").reasoning_field == "reasoning_content"


def test_unavailable_is_unknown_not_fake():
    from modelcheck.core.types import Verdict
    from modelcheck.core.engine import decide
    from modelcheck.checks.model_field.check import ModelField
    t = Target("https://x", "k" * 20, "openai/gpt-5.4-mini", "openai")
    res = ModelField().run(Fake(lambda m, ms, kw: Reply(status=502, error="upstream unavailable")), t, "openai")
    assert res[0].status is Status.SKIP
    assert decide(res)[0] is Verdict.UNKNOWN


def test_forty_loglik_prefers_own_profile():
    ref_a = {"Name a color.": {"blue": 8}}
    ref_b = {"Name a color.": {"lavender": 8}}
    got = {"Name a color.": Counter({"lavender": 4})}
    assert loglik(got, ref_b) > loglik(got, ref_a)
