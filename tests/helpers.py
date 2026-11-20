"""Общие заготовки для тестов: поддельный клиент и «модель», которая отвечает по смыслу вопроса."""
from __future__ import annotations

import re

from modelcheck.core.client import Reply


class Fake:
    """Клиент без сети: chat() и responses() отдают то, что вернёт переданная функция."""

    def __init__(self, fn, resp=None):
        self.fn, self.resp, self.count = fn, resp, 0

    def chat(self, model, messages, **kw):
        self.count += 1
        return self.fn(model, messages, kw)

    def responses(self, model, text, **kw):
        return self.resp(model, text, kw) if self.resp else Reply(status=404, error="not found")


def ok(**kw) -> Reply:
    return Reply(status=200, **kw)


def model_stub(who="I am Claude by Anthropic.", stops_on=(), obeys_system=True):
    """Поддельная модель.

    who       — что отвечает на «кто ты» (строка или итератор строк);
    stops_on  — служебные токены, на которых модель обрывает ответ (её «родные»);
    """
    who_iter = iter(who) if not isinstance(who, str) else None

    def fn(model, messages, kw):
        q = messages[-1]["content"]
        system = kw.get("system") or ""
        if "Кодовое слово" in system:
            code = re.search(r"Кодовое слово: (\S+?)\.", system).group(1)
            return ok(text=code if obeys_system else "Не знаю")
        for tok in stops_on:
            if tok in q:
                return ok(text=q.split(tok)[0].split()[-1])         # оборвались на своём токене
        m = re.search(r"(?:кавычках: \"|изменений: |текст: «)(.+?)[\"»]?$", q)
        if m:
            return ok(text=m.group(1))                              # честно повторили строку
        if re.search(r"фрукт|город|радуг", q):
            return ok(text="яблоко, груша, слива")
        return ok(text=next(who_iter) if who_iter else who)
    return fn
