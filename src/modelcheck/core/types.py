"""Общие типы: цель проверки, результат одной проверки, итоговый отчёт.

Вердикт двухосевой (как в api-scam-hunter): «настоящая ли модель» и «честно ли
обслуживают». Скрытый промпт на 4000 токенов — это переплата и вмешательство,
но модель внутри при этом может быть настоящей. Это разные вопросы.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class Status(str, Enum):
    PASS = "pass"   # признак настоящей модели / честного сервиса
    WARN = "warn"   # подозрительно, но не доказательство
    FAIL = "fail"   # признак подмены / нарушения
    INFO = "info"   # просто факт (посредник, скорость)
    SKIP = "skip"   # проверка неприменима или не удалась


class Axis(str, Enum):
    MODEL = "model"       # что за модель отвечает
    SERVICE = "service"   # честно ли обслуживает посредник: скрытый промпт, параметры, урезания


class Verdict(str, Enum):
    GENUINE = "genuine"
    SUSPICIOUS = "suspicious"
    FAKE = "fake"
    UNKNOWN = "unknown"


class ServiceVerdict(str, Enum):
    CLEAN = "clean"
    INTERFERES = "interferes"   # вмешивается: скрытый промпт, игнор параметров, урезанные возможности
    UNKNOWN = "unknown"


@dataclass
class Finding:
    check: str
    status: Status
    title: str
    detail: str = ""
    critical: bool = False          # одного такого FAIL достаточно для «подмены»
    evidence: dict = field(default_factory=dict)
    axis: Axis = Axis.MODEL


@dataclass
class Target:
    base_url: str
    api_key: str
    model: str
    protocol: str                    # "anthropic" | "openai"

    @property
    def masked_key(self) -> str:
        k = self.api_key
        return k[:4] + "…" + k[-4:] if len(k) > 12 else "***"


@dataclass
class Report:
    target: Target
    maker: str
    findings: list[Finding]
    verdict: Verdict
    score: int
    elapsed: float
    requests: int
    service: ServiceVerdict = ServiceVerdict.UNKNOWN
    seed: int = 0
    runs: int = 1


def svc(check: str, status: Status, title: str, detail: str = "", **kw) -> Finding:
    """Находка про честность обслуживания (ось SERVICE)."""
    return Finding(check, status, title, detail, axis=Axis.SERVICE, **kw)
