"""Запуск проверок и итоговый вердикт по двум осям.

Ось MODEL — «настоящая ли модель». «Подмена» только при сильной улике (critical)
или двух независимых провалах; одиночный слабый сигнал даёт «подозрительно».
Ось SERVICE — «честно ли обслуживают»: скрытый промпт, игнор параметров, урезания.
Недоступный сервис (502, таймаут) — «нет данных», а не обвинение.
"""
from __future__ import annotations

import time

from ..makers import maker_of
from . import rand
from .check import REGISTRY
from .client import make_client
from .types import Axis, Finding, Report, ServiceVerdict, Status, Target, Verdict

WEIGHT = {Status.PASS: 1.0, Status.WARN: 0.4, Status.FAIL: 0.0}


def detect_protocol(model: str, base_url: str) -> str:
    return "anthropic" if "anthropic.com" in base_url else "openai"


def decide(findings: list[Finding]) -> tuple[Verdict, int]:
    if any(f.evidence.get("unavailable") for f in findings):
        return Verdict.UNKNOWN, 0
    scored = [f for f in findings if f.status in WEIGHT and f.axis is Axis.MODEL]
    if not scored:
        return Verdict.UNKNOWN, 0
    score = round(100 * sum(WEIGHT[f.status] for f in scored) / len(scored))
    fails = [f for f in scored if f.status is Status.FAIL]
    if any(f.critical for f in fails) or len({f.check for f in fails}) >= 2:
        return Verdict.FAKE, min(score, 30)
    if fails or sum(f.status is Status.WARN for f in scored) >= 3:
        return Verdict.SUSPICIOUS, min(score, 70)
    return Verdict.GENUINE, score


def decide_service(findings: list[Finding]) -> ServiceVerdict:
    svc = [f for f in findings if f.axis is Axis.SERVICE and f.status in WEIGHT]
    if not svc:
        return ServiceVerdict.UNKNOWN
    return ServiceVerdict.INTERFERES if any(f.status in (Status.FAIL, Status.WARN) for f in svc) else ServiceVerdict.CLEAN


def run(target: Target, level: int = 2, only: list[str] | None = None, on_step=None,
        seed: int | None = None, timeout: float = 45) -> Report:
    used_seed = rand.seed(seed)
    maker = maker_of(target.model)
    client = make_client(target.protocol, target.base_url, target.api_key, timeout=timeout)
    findings: list[Finding] = []
    t = time.perf_counter()
    for cls in REGISTRY:
        chk = cls()
        if only and chk.name not in only:
            continue
        if not only and chk.level > level:
            continue
        if not chk.applies(target, maker):
            continue
        if on_step:
            on_step(chk.title)
        try:
            findings += chk.run(client, target, maker)
        except Exception as e:  # одна сломанная проверка не валит весь отчёт
            findings.append(Finding(chk.name, Status.SKIP, chk.title, f"Ошибка проверки: {type(e).__name__}: {e}"))
        if any(f.evidence.get("unavailable") for f in findings):
            break                # сервис лежит — дальше только тратить запросы
    verdict, score = decide(findings)
    return Report(target, maker, findings, verdict, score, time.perf_counter() - t, client.count,
                  service=decide_service(findings), seed=used_seed)


def run_many(target: Target, times: int, **kw) -> Report:
    """Несколько прогонов подряд с разными сидами (у пула аккаунтов запросы уходят на разные бэкенды).

    Итог — худший вердикт по модели; у каждого провала видно, в скольких прогонах он повторился.
    """
    kw.pop("seed", None)
    reports = [run(target, **kw) for _ in range(times)]
    order = [Verdict.FAKE, Verdict.SUSPICIOUS, Verdict.GENUINE, Verdict.UNKNOWN]
    worst = min(reports, key=lambda r: order.index(r.verdict))
    seen: dict[tuple, int] = {}
    for r in reports:
        for key in {(f.check, f.title, f.status) for f in r.findings}:
            seen[key] = seen.get(key, 0) + 1
    if times > 1:
        for f in worst.findings:
            if f.status in (Status.FAIL, Status.WARN):
                f.detail += f"  [в {seen.get((f.check, f.title, f.status), 1)} из {times} прогонов]"
    worst.runs = times
    worst.requests = sum(r.requests for r in reports)
    worst.elapsed = sum(r.elapsed for r in reports)
    if any(r.service is ServiceVerdict.INTERFERES for r in reports):
        worst.service = ServiceVerdict.INTERFERES
    return worst
