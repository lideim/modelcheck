"""Тесты движка: две оси вердикта, рандомизация, эталоны, поздние ходы, повторные прогоны."""
from __future__ import annotations

import json

from helpers import Fake, ok, model_stub

from modelcheck.checks.hidden_prompt.check import HiddenPrompt
from modelcheck.checks.late_turns.check import LateTurns
from modelcheck.checks.reasoning.check import make_task
from modelcheck.core import baselines, rand
from modelcheck.core.client import Reply
from modelcheck.core.engine import decide, decide_service, run_many
from modelcheck.core.types import Axis, Finding, ServiceVerdict, Status, Target, Verdict, svc

T = Target("https://x", "k" * 20, "anthropic/claude-opus-4.8", "openai")


def test_hidden_prompt_is_service_axis_not_fake():
    r = ok(text="x", usage={"prompt_tokens": 4064, "completion_tokens": 3})
    res = HiddenPrompt().run(Fake(lambda m, ms, kw: r), T, "anthropic")
    assert res[0].axis is Axis.SERVICE and res[0].status is Status.FAIL
    assert decide(res)[0] is Verdict.UNKNOWN          # по оси модели данных нет — не «подмена»
    assert decide_service(res) is ServiceVerdict.INTERFERES


def test_service_clean():
    assert decide_service([svc("x", Status.PASS, "a")]) is ServiceVerdict.CLEAN


def test_seed_reproducible():
    rand.seed(42)
    a = [rand.word(), make_task()]
    rand.seed(42)
    assert [rand.word(), make_task()] == a
    rand.seed(43)
    assert rand.word() != a[0]


def test_task_answer_is_correct():
    rand.seed(7)
    q, answer = make_task()
    import re
    s = int(re.search(r"(\d) сестры", q).group(1))
    assert answer == str(s - 1)


def test_baselines_save_load_and_stale(tmp_path, monkeypatch):
    monkeypatch.setenv("MODELCHECK_HOME", str(tmp_path))
    baselines.save("anthropic/claude-x", {"maker": "anthropic", "tokens": {"en": 17}})
    data = baselines.load("tokens")
    assert "anthropic/claude-x" in data and data["anthropic/claude-x"]["date"]
    assert baselines.stale_note(data["anthropic/claude-x"]) == ""
    assert "устарел" in baselines.stale_note({"date": "2020-01-01"})
    assert baselines.load("forty") == {}
    f = next(tmp_path.glob("baselines/*.json"))
    assert json.loads(f.read_text())


def test_late_turns_model_switch_is_critical():
    def fn(m, ms, kw):
        return ok(text="Код повторю: ..., первый вопрос был про список. Я Claude.", model="qwen2.5-7b-instruct")
    res = LateTurns().run(Fake(fn), T, "anthropic")
    assert any(f.status is Status.FAIL and f.critical for f in res)


def test_late_turns_clean():
    def fn(m, ms, kw):
        q = ms[-1]["content"]
        import re
        code = re.search(r"Повтори код: (\S+?)\.", q).group(1)
        first = ms[0]["content"]
        return ok(text=f"1) {code} 2) {first} 3) Claude от Anthropic.", model="claude-opus-4-8")
    res = LateTurns().run(Fake(fn), T, "anthropic")
    assert res[0].status is Status.PASS


def test_run_many_marks_repeats(monkeypatch):
    import modelcheck.core.engine as eng
    from modelcheck.core.types import Report

    def fake_run(target, **kw):
        f = Finding("x", Status.WARN, "Кто ты?", "путается")
        return Report(target, "anthropic", [f], Verdict.SUSPICIOUS, 60, 1.0, 5)
    monkeypatch.setattr(eng, "run", fake_run)
    rep = run_many(T, 3)
    assert rep.runs == 3 and rep.requests == 15
    assert "в 3 из 3 прогонов" in rep.findings[0].detail
