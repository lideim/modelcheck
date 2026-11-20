"""HTTP-клиенты для двух протоколов. Проверки не знают про URL — только про Reply."""
from __future__ import annotations

import time
from dataclasses import dataclass, field

import httpx


@dataclass
class Reply:
    status: int
    text: str = ""                       # итоговый текст ответа
    model: str = ""                      # поле model из ответа
    id: str = ""                         # id ответа
    usage: dict = field(default_factory=dict)
    thinking: list[dict] = field(default_factory=list)   # блоки размышлений (anthropic)
    tool_calls: list[dict] = field(default_factory=list)
    extra: dict = field(default_factory=dict)            # нестандартные поля (reasoning_content, system_fingerprint)
    headers: dict = field(default_factory=dict)
    raw: dict = field(default_factory=dict)
    error: str = ""
    latency: float = 0.0

    @property
    def ok(self) -> bool:
        return 200 <= self.status < 300 and not self.error


class Client:
    """Базовый клиент: считает запросы, ловит сетевые ошибки."""

    def __init__(self, base_url: str, api_key: str, timeout: float = 45, retries: int = 2):
        self.base = base_url.rstrip("/")
        if self.base.endswith("/v1"):
            self.base = self.base[:-3]
        self.key = api_key
        self.http = httpx.Client(timeout=timeout, headers={"user-agent": "modelcheck"})
        self.retries = retries
        self.count = 0

    def _post(self, path: str, headers: dict, body: dict) -> tuple[int, dict, dict, float, str]:
        """POST с повтором на временные сбои (429, 5xx, обрыв): флапающий сервис ≠ подмена."""
        for attempt in range(self.retries + 1):
            self.count += 1
            t = time.perf_counter()
            try:
                r = self.http.post(self.base + path, headers=headers, json=body)
            except httpx.HTTPError as e:
                if attempt < self.retries:
                    time.sleep(1.5 * (attempt + 1))
                    continue
                return 0, {}, {}, time.perf_counter() - t, f"{type(e).__name__}: {e}"
            dt = time.perf_counter() - t
            if (r.status_code == 429 or r.status_code >= 500) and attempt < self.retries:
                time.sleep(1.5 * (attempt + 1))
                continue
            try:
                return r.status_code, r.json(), dict(r.headers), dt, ""
            except ValueError:
                return r.status_code, {}, dict(r.headers), dt, f"не JSON: {r.text[:200]}"
        return 0, {}, {}, 0.0, "нет ответа"

    def models(self) -> tuple[int, dict]:
        self.count += 1
        try:
            r = self.http.get(self.base + "/v1/models", headers=self._auth())
            return r.status_code, (r.json() if r.headers.get("content-type", "").startswith("application/json") else {})
        except (httpx.HTTPError, ValueError):
            return 0, {}

    def _auth(self) -> dict:
        raise NotImplementedError

    def chat(self, model: str, messages: list[dict], **kw) -> Reply:
        raise NotImplementedError


class AnthropicClient(Client):
    def _auth(self) -> dict:
        return {"x-api-key": self.key, "anthropic-version": "2023-06-01", "content-type": "application/json"}

    def chat(self, model, messages, max_tokens=300, system=None, thinking=None, tools=None, temperature=None, **_) -> Reply:
        body = {"model": model, "max_tokens": max_tokens, "messages": messages}
        if system:
            body["system"] = system
        if thinking:
            body["thinking"] = {"type": "enabled", "budget_tokens": thinking}
        if tools:
            body["tools"] = tools
        if temperature is not None and not thinking:
            body["temperature"] = temperature
        st, d, h, dt, err = self._post("/v1/messages", self._auth(), body)
        rep = Reply(status=st, raw=d, headers=h, latency=dt, error=err)
        if err or "content" not in d:
            rep.error = rep.error or _err(d)
            return rep
        for b in d.get("content", []):
            if b.get("type") == "text":
                rep.text += b.get("text", "")
            elif b.get("type") in ("thinking", "redacted_thinking"):
                rep.thinking.append(b)
            elif b.get("type") == "tool_use":
                rep.tool_calls.append(b)
        rep.model, rep.id, rep.usage = d.get("model", ""), d.get("id", ""), d.get("usage") or {}
        return rep


class OpenAIClient(Client):
    def _auth(self) -> dict:
        return {"Authorization": f"Bearer {self.key}", "content-type": "application/json"}

    def chat(self, model, messages, max_tokens=300, system=None, thinking=None, tools=None, temperature=None, **_) -> Reply:
        msgs = ([{"role": "system", "content": system}] if system else []) + messages
        body = {"model": model, "max_tokens": max_tokens, "messages": msgs}
        if tools:
            body["tools"] = [{"type": "function", "function": {"name": t["name"], "description": t["description"],
                                                               "parameters": t["input_schema"]}} for t in tools]
        if temperature is not None:
            body["temperature"] = temperature
        st, d, h, dt, err = self._post("/v1/chat/completions", self._auth(), body)
        rep = Reply(status=st, raw=d, headers=h, latency=dt, error=err)
        if err or not d.get("choices"):
            rep.error = rep.error or _err(d)
            return rep
        msg = d["choices"][0].get("message") or {}
        rep.text = msg.get("content") or ""
        rep.tool_calls = msg.get("tool_calls") or []
        rep.model, rep.id, rep.usage = d.get("model", ""), d.get("id", ""), d.get("usage") or {}
        for k in ("reasoning_content", "reasoning"):
            if msg.get(k):
                rep.extra[k] = msg[k]
        if "system_fingerprint" in d:
            rep.extra["system_fingerprint"] = d["system_fingerprint"]
        return rep

    def responses(self, model, text, include_encrypted=False, previous_items=None) -> Reply:
        """OpenAI / xAI Responses API (/v1/responses) — нужен для проверки зашифрованных размышлений."""
        inp = list(previous_items or []) + [{"role": "user", "content": text}]
        body = {"model": model, "input": inp, "store": False, "max_output_tokens": 2000}
        if include_encrypted:
            body["include"] = ["reasoning.encrypted_content"]
            body["reasoning"] = {"effort": "low"}
        st, d, h, dt, err = self._post("/v1/responses", self._auth(), body)
        rep = Reply(status=st, raw=d, headers=h, latency=dt, error=err)
        if err or "output" not in d:
            rep.error = rep.error or _err(d)
            return rep
        items = d.get("output") or []
        rep.extra["output_items"] = items
        for it in items:
            if it.get("type") == "reasoning" and it.get("encrypted_content"):
                rep.extra["encrypted_reasoning"] = it["encrypted_content"]
            if it.get("type") == "message":
                for c in it.get("content") or []:
                    rep.text += c.get("text", "")
        rep.model, rep.id, rep.usage = d.get("model", ""), d.get("id", ""), d.get("usage") or {}
        return rep


def _err(d: dict) -> str:
    e = d.get("error") if isinstance(d, dict) else None
    if isinstance(e, dict):
        return e.get("message") or e.get("type") or str(e)
    return str(e or d)[:200]


def make_client(protocol: str, base_url: str, api_key: str, timeout: float = 45) -> Client:
    cls = AnthropicClient if protocol == "anthropic" else OpenAIClient
    return cls(base_url, api_key, timeout=timeout)
