"""Эталоны: снятые с ЗАВЕДОМО настоящего ключа отпечатки модели.

Хранятся в ~/.modelcheck/baselines/<имя>.json (папку можно сменить переменной
MODELCHECK_HOME). У каждого эталона есть дата: модели обновляются, токенизатор и
привычки меняются, поэтому эталон старше MAX_AGE_DAYS помечается как устаревший.
"""
from __future__ import annotations

import json
import os
from datetime import date, datetime
from pathlib import Path

MAX_AGE_DAYS = 90


def home() -> Path:
    return Path(os.environ.get("MODELCHECK_HOME", Path.home() / ".modelcheck"))


def base_dir() -> Path:
    return home() / "baselines"


def load(kind: str | None = None) -> dict[str, dict]:
    """Все эталоны; kind — оставить только те, где есть этот раздел (tokens / numbers / forty)."""
    out: dict[str, dict] = {}
    d = base_dir()
    if d.exists():
        for p in sorted(d.glob("*.json")):
            try:
                out.update(json.loads(p.read_text(encoding="utf-8")))
            except (ValueError, OSError):
                continue
    return {k: v for k, v in out.items() if not kind or v.get(kind)}


def save(name: str, entry: dict) -> Path:
    d = base_dir()
    d.mkdir(parents=True, exist_ok=True)
    entry = {**entry, "date": date.today().isoformat()}
    f = d / f"{name.replace('/', '_')}.json"
    f.write_text(json.dumps({name: entry}, ensure_ascii=False, indent=1), encoding="utf-8")
    return f


def age_days(entry: dict) -> int | None:
    try:
        return (date.today() - datetime.fromisoformat(entry["date"]).date()).days
    except (KeyError, ValueError):
        return None


def stale_note(entry: dict) -> str:
    a = age_days(entry)
    if a is None:
        return " (дата эталона неизвестна)"
    if a > MAX_AGE_DAYS:
        return f" (эталон устарел: {a} дн., модель могла обновиться — сними заново)"
    return ""
