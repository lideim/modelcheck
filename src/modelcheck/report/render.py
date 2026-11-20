"""Вывод отчёта: терминал (rich), JSON и Markdown (можно приложить к жалобе в поддержку).

Два вердикта: «модель» (настоящая ли) и «обслуживание» (вмешивается ли посредник).
"""
from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from ..core.types import Axis, Report, ServiceVerdict, Status, Verdict

ICON = {Status.PASS: "[green]✔[/]", Status.WARN: "[yellow]▲[/]", Status.FAIL: "[red]✖[/]",
        Status.INFO: "[cyan]i[/]", Status.SKIP: "[dim]–[/]"}
SYM = {Status.PASS: "✅", Status.WARN: "⚠️", Status.FAIL: "❌", Status.INFO: "ℹ️", Status.SKIP: "—"}
VERDICT = {
    Verdict.GENUINE: ("green", "✅ Модель: похоже на настоящую"),
    Verdict.SUSPICIOUS: ("yellow", "⚠️  Модель: подозрительно"),
    Verdict.FAKE: ("red", "❌ Модель: признаки подмены"),
    Verdict.UNKNOWN: ("white", "❔ Модель: недостаточно данных"),
}
SERVICE = {
    ServiceVerdict.CLEAN: ("green", "✅ Обслуживание: без вмешательства"),
    ServiceVerdict.INTERFERES: ("yellow", "⚠️  Обслуживание: посредник вмешивается (скрытый промпт / параметры / урезания)"),
    ServiceVerdict.UNKNOWN: ("white", "❔ Обслуживание: нет данных"),
}


def _footer(rep: Report) -> str:
    runs = f"{rep.runs} прогона · " if rep.runs > 1 else ""
    return (f"{runs}{rep.requests} запросов · {rep.elapsed:.0f} с · сид {rep.seed} · "
            "один прогон — не приговор: проверяй в разное время")


def to_console(rep: Report, console: Console | None = None, short: bool = False) -> None:
    c = console or Console()
    t = rep.target
    if not short:
        c.print(f"\n[bold]modelcheck[/] · {t.base_url} · [cyan]{t.model}[/] · ключ {t.masked_key} · "
                f"протокол {t.protocol} · производитель [bold]{rep.maker}[/]\n")
        for axis, head in ((Axis.MODEL, "Что за модель"), (Axis.SERVICE, "Честность обслуживания")):
            rows = [f for f in rep.findings if f.axis is axis]
            if not rows:
                continue
            tab = Table(title=head, title_justify="left", title_style="bold", show_header=False,
                        box=None, pad_edge=False)
            tab.add_column(width=2)
            tab.add_column(style="bold", min_width=26)
            tab.add_column()
            for f in rows:
                tab.add_row(ICON[f.status], f.title, f.detail)
            c.print(tab)
            c.print()
    mc, mt = VERDICT[rep.verdict]
    sc, stext = SERVICE[rep.service]
    border = "red" if rep.verdict is Verdict.FAKE else mc if rep.verdict is not Verdict.GENUINE else sc
    label = f"[dim]{t.model}[/]\n" if short else ""
    c.print(Panel(f"{label}[bold {mc}]{mt}[/]   оценка {rep.score}/100\n[bold {sc}]{stext}[/]\n[dim]{_footer(rep)}[/]",
                  border_style=border))


def to_json(rep: Report) -> str:
    d = asdict(rep)
    d["target"]["api_key"] = rep.target.masked_key
    return json.dumps(d, ensure_ascii=False, indent=2, default=str)


def to_markdown(rep: Report) -> str:
    t = rep.target
    lines = ["# Отчёт modelcheck", "",
             f"- **Эндпоинт:** `{t.base_url}`", f"- **Модель:** `{t.model}` ({rep.maker})",
             f"- **Ключ:** `{t.masked_key}`",
             f"- **{VERDICT[rep.verdict][1]}** — {rep.score}/100", f"- **{SERVICE[rep.service][1]}**",
             f"- {_footer(rep)}", ""]
    for axis, head in ((Axis.MODEL, "Что за модель"), (Axis.SERVICE, "Честность обслуживания")):
        rows = [f for f in rep.findings if f.axis is axis]
        if rows:
            lines += [f"## {head}", "", "| | Проверка | Результат |", "|---|---|---|"]
            lines += [f"| {SYM[f.status]} | {f.title} | {f.detail.replace('|', '/')} |" for f in rows]
            lines.append("")
    return "\n".join(lines)


def history_table(log: Path) -> Table:
    tab = Table(title=f"История: {log}", box=None)
    for c in ("Время", "Модель", "Обслуживание", "Оценка", "Провалы"):
        tab.add_column(c)
    if log.exists():
        for line in log.read_text(encoding="utf-8").splitlines()[-30:]:
            r = json.loads(line)
            v = Verdict(r["verdict"])
            tab.add_row(r["time"], VERDICT[v][1].split(": ")[1], r.get("service", ""), str(r["score"]),
                        ", ".join(r.get("fails", [])) or "—")
    return tab
