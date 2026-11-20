"""Командная строка modelcheck.

  run       проверить ключ и модель
  watch     проверять по расписанию и писать историю (ловит подмену в часы пик)
  baseline  снять эталон с ЗАВЕДОМО настоящего ключа
  list      какие есть проверки
  makers    какие производители поддерживаются
"""
from __future__ import annotations

import json
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from . import __version__, checks  # noqa: F401  (регистрирует все проверки)
from .core import baselines
from .core.check import REGISTRY
from .core.engine import detect_protocol, run as run_checks, run_many
from .core.types import Target, Verdict
from .makers import PROFILES, maker_of
from .report import render

app = typer.Typer(add_completion=False, no_args_is_help=True,
                  help="modelcheck — настоящая ли нейросеть за API-ключом.")
con = Console()
LEVELS = {"quick": 1, "standard": 2, "full": 3}
EXIT = {Verdict.GENUINE: 0, Verdict.SUSPICIOUS: 1, Verdict.FAKE: 2, Verdict.UNKNOWN: 3}

URL = typer.Argument(..., help="Адрес API, например https://api.example.com/v1")
MODEL = typer.Option(..., "--model", "-m", help="Заявленная модель, как у провайдера (anthropic/claude-opus-4.8)")
KEY = typer.Option(None, "--key", "-k", help="API-ключ. Лучше через переменную MODELCHECK_KEY")
PROTO = typer.Option(None, "--protocol", "-p", help="anthropic | openai. По умолчанию openai, кроме api.anthropic.com")
TIMEOUT = typer.Option(45.0, "--timeout", help="Таймаут одного запроса, сек")


def _target(url, key, model, protocol) -> Target:
    key = key or os.environ.get("MODELCHECK_KEY", "")
    if not key:
        raise typer.BadParameter("Нужен ключ: --key или переменная окружения MODELCHECK_KEY")
    if protocol and protocol not in ("anthropic", "openai"):
        raise typer.BadParameter("--protocol: anthropic или openai")
    return Target(url, key, model, protocol or detect_protocol(model, url))


def _version(v: bool):
    if v:
        con.print(f"modelcheck {__version__}")
        raise typer.Exit()


@app.callback()
def main_cb(version: bool = typer.Option(False, "--version", "-V", callback=_version, is_eager=True,
                                         help="Показать версию")):
    pass


@app.command()
def run(
    url: str = URL, model: str = MODEL, key: Optional[str] = KEY, protocol: Optional[str] = PROTO,
    level: str = typer.Option("standard", "--level", "-l", help="quick | standard | full"),
    times: int = typer.Option(1, "--times", "-n", min=1, max=10, help="Сколько прогонов подряд (для пулов аккаунтов)"),
    only: Optional[str] = typer.Option(None, "--only", help="Только эти проверки, через запятую (см. modelcheck list)"),
    seed: Optional[int] = typer.Option(None, "--seed", help="Сид случайных формулировок (повторить прогон один в один)"),
    timeout: float = TIMEOUT,
    json_out: Optional[Path] = typer.Option(None, "--json", help="Сохранить отчёт в JSON"),
    md_out: Optional[Path] = typer.Option(None, "--md", help="Сохранить отчёт в Markdown"),
    quiet: bool = typer.Option(False, "--quiet", "-q", help="Без таблицы, только вердикт"),
):
    """Проверить ключ и модель. Код выхода: 0 настоящая, 1 подозрительно, 2 подмена, 3 нет данных."""
    if level not in LEVELS:
        raise typer.BadParameter("--level: quick, standard или full")
    t = _target(url, key, model, protocol)
    kw = dict(level=LEVELS[level], only=only.split(",") if only else None, timeout=timeout)
    with con.status("Проверяю…") as st:
        kw["on_step"] = lambda s: st.update(f"Проверяю: {s}")
        rep = run_many(t, times, **kw) if times > 1 else run_checks(t, seed=seed, **kw)
    render.to_console(rep, con, short=quiet)
    if json_out:
        json_out.write_text(render.to_json(rep), encoding="utf-8")
    if md_out:
        md_out.write_text(render.to_markdown(rep), encoding="utf-8")
    raise typer.Exit(EXIT[rep.verdict])


@app.command()
def watch(
    url: str = URL, model: str = MODEL, key: Optional[str] = KEY, protocol: Optional[str] = PROTO,
    every: int = typer.Option(60, "--every", help="Интервал между проверками, минут"),
    count: int = typer.Option(0, "--count", help="Сколько проверок сделать (0 — пока не остановишь Ctrl+C)"),
    level: str = typer.Option("quick", "--level", "-l"),
    log: Path = typer.Option(Path("modelcheck-history.jsonl"), "--log", help="Файл истории (по строке на проверку)"),
    timeout: float = TIMEOUT,
):
    """Проверять по расписанию: подмену иногда включают только в часы пик."""
    t = _target(url, key, model, protocol)
    n = 0
    con.print(f"Слежу за [cyan]{t.model}[/] каждые {every} мин → {log}  (Ctrl+C — стоп)")
    try:
        while True:
            rep = run_checks(t, LEVELS[level], timeout=timeout)
            row = {"time": datetime.now().isoformat(timespec="seconds"), "model": t.model,
                   "verdict": rep.verdict.value, "service": rep.service.value, "score": rep.score,
                   "fails": [f.title for f in rep.findings if f.status.value == "fail"]}
            with log.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(row, ensure_ascii=False) + "\n")
            render.to_console(rep, con, short=True)
            n += 1
            if count and n >= count:
                break
            time.sleep(every * 60)
    except KeyboardInterrupt:
        pass
    con.print(render.history_table(log))


@app.command()
def baseline(
    url: str = URL, model: str = MODEL, key: Optional[str] = KEY, protocol: Optional[str] = PROTO,
    full: bool = typer.Option(False, "--full", help="Ещё «случайное число» и «сорок вопросов» (~70 запросов)"),
    name: Optional[str] = typer.Option(None, "--name", help="Имя эталона (по умолчанию — имя модели)"),
    timeout: float = TIMEOUT,
):
    """Снять эталон с ЗАВЕДОМО НАСТОЯЩЕГО ключа (официальный API производителя)."""
    from .checks.forty_questions.check import ask_all
    from .checks.random_number.check import sample
    from .checks.tokenizer.check import measure
    from .core.client import make_client
    t = _target(url, key, model, protocol)
    cl = make_client(t.protocol, t.base_url, t.api_key, timeout=timeout)
    entry: dict = {"maker": maker_of(t.model), "protocol": t.protocol, "source": t.base_url}
    with con.status("Снимаю токенизатор…") as st:
        tok = measure(cl, t.model)
        if tok:
            entry["tokens"] = tok
        else:
            con.print("[yellow]Счётчик токенов нестабилен — токенизатор пропущен.[/]")
        if full:
            st.update("Снимаю «случайное число»…")
            entry["numbers"] = dict(sample(cl, t.model))
            st.update("Снимаю «сорок вопросов»…")
            entry["forty"] = {q: dict(c) for q, c in ask_all(cl, t.model).items()}
    parts = [k for k in ("tokens", "numbers", "forty") if k in entry]
    if not parts:
        con.print("[red]Ничего снять не удалось.[/]")
        raise typer.Exit(1)
    f = baselines.save(name or t.model, entry)
    con.print(f"[green]Эталон сохранён:[/] {f}  ({', '.join(parts)})")


@app.command("baselines")
def list_baselines():
    """Какие эталоны сохранены и не устарели ли они."""
    data = baselines.load()
    if not data:
        con.print(f"Эталонов нет. Папка: {baselines.base_dir()}")
        return
    tab = Table(box=None)
    for c in ("Эталон", "Производитель", "Что есть", "Дата", "Состояние"):
        tab.add_column(c)
    for n, v in sorted(data.items()):
        age = baselines.age_days(v)
        state = "—" if age is None else ("[red]устарел[/]" if age > baselines.MAX_AGE_DAYS else f"{age} дн.")
        tab.add_row(n, v.get("maker", "?"), ", ".join(k for k in ("tokens", "numbers", "forty") if k in v),
                    v.get("date", "?"), state)
    con.print(tab)


@app.command("list")
def list_checks():
    """Какие есть проверки."""
    names = {1: "quick", 2: "standard", 3: "full"}
    tab = Table(box=None)
    for c in ("Проверка", "Уровень", "Описание", "Для кого"):
        tab.add_column(c)
    for cls in REGISTRY:
        tab.add_row(f"[cyan]{cls.name}[/]", names[cls.level], cls.title,
                    "/".join(cls.protocols) + (" · " + ",".join(cls.makers) if cls.makers else " · все"))
    con.print(tab)


@app.command("makers")
def list_makers():
    """Какие производители поддерживаются и что у кого можно проверить."""
    tab = Table(box=None)
    for c in ("Производитель", "Подпись размышлений", "Поле размышлений", "Стоп-токен", "Открытые веса"):
        tab.add_column(c)
    sig = {"anthropic_thinking": "★★★ thinking", "openai_encrypted": "★★ encrypted", "xai_encrypted": "★★ encrypted",
           "gemini_thought": "★★ thoughtSignature"}
    for p in sorted(PROFILES.values(), key=lambda p: (p.signature is None, p.name)):
        tab.add_row(p.title, sig.get(p.signature, "—"), p.reasoning_field or "—",
                    p.special_tokens[0] if p.special_tokens else "—", "да" if p.open_weights else "")
    con.print(tab)


def main():
    app()


if __name__ == "__main__":
    main()
