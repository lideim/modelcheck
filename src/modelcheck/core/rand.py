"""Рандомизация проверочных запросов.

Если посредник выучит наши тестовые фразы, он сможет отправлять именно их на настоящую
модель, а остальной трафик — на дешёвую. Поэтому каждый прогон собирает фразы заново:
случайная формулировка + случайная «обычная» обёртка, так что запрос похож на рабочий.
Сид печатается в отчёте — прогон можно повторить один в один (--seed).
"""
from __future__ import annotations

import random

_rng = random.Random()

# обычные рабочие фразы, в которые прячем проверку
COVERS = [
    "", "", "",  # иногда без обёртки
    "Работаю над ботом, вопрос по ходу. ",
    "Небольшой вопрос между делом: ",
    "Пишу заметку, уточни, пожалуйста. ",
    "Quick one while I'm debugging: ",
    "Сейчас разбираюсь с API. ",
]


def seed(value: int | None) -> int:
    s = value if value is not None else random.randrange(1, 10**9)
    _rng.seed(s)
    return s


def pick(options: list[str]) -> str:
    return _rng.choice(options)


def cover(text: str) -> str:
    """Обернуть проверочный вопрос в «обычный» контекст."""
    return _rng.choice(COVERS) + text


def word(n: int = 5) -> str:
    """Случайное кодовое слово (для канареек)."""
    return "".join(_rng.choice("АБВГДЕЖЗИКЛМНОПРСТУФХ") for _ in range(n)) + "-" + str(_rng.randint(1000, 9999))


def number(a: int, b: int) -> int:
    return _rng.randint(a, b)


def shuffle(seq: list) -> list:
    out = list(seq)
    _rng.shuffle(out)
    return out
