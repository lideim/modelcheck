"""Базовый класс проверки и реестр всех проверок."""
from __future__ import annotations

from abc import ABC, abstractmethod

from .client import Client
from .types import Finding, Target


class Check(ABC):
    name: str = ""                 # id проверки (папка)
    title: str = ""                # по-русски для отчёта
    protocols: tuple[str, ...] = ("anthropic", "openai")
    makers: tuple[str, ...] = ()   # пусто = для всех производителей
    level: int = 1                 # 1 быстрая, 2 стандарт, 3 полная (дороже)

    def applies(self, target: Target, maker: str) -> bool:
        return target.protocol in self.protocols and (not self.makers or maker in self.makers)

    @abstractmethod
    def run(self, client: Client, target: Target, maker: str) -> list[Finding]:
        ...


REGISTRY: list[type[Check]] = []


def register(cls: type[Check]) -> type[Check]:
    REGISTRY.append(cls)
    return cls
