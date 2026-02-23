import json
import re
from typing import Any
from urllib.parse import urlparse

import requests


def check_http(url: str, timeout: int = 4) -> tuple[bool, str]:
    if not url:
        return (False, "empty url")
    candidate = str(url).strip()
    parsed = urlparse(candidate)
    if not parsed.scheme:
        candidate = f"http://{candidate}"
    try:
        r = requests.get(candidate, timeout=timeout)
        return (r.ok, f"HTTP {r.status_code}")
    except Exception as e:
        return (False, str(e))


def _provider_v1_base(base_url: str) -> str:
    base = str(base_url or "").strip().rstrip("/")
    if not base:
        return ""
    if not urlparse(base).scheme:
        base = f"http://{base}"
    if not base.endswith("/v1"):
        base = f"{base}/v1"
    return base


def _provider_models(base_url: str, api_key: str = "", timeout: int = 12) -> tuple[list[str], str]:
    base = _provider_v1_base(base_url)
    if not base:
        return ([], "empty base_url")
    url = f"{base}/models"
    headers: dict[str, str] = {}
    if str(api_key or "").strip():
        headers["Authorization"] = f"Bearer {str(api_key).strip()}"
    try:
        r = requests.get(url, headers=headers, timeout=timeout)
        r.raise_for_status()
        obj = r.json() if "application/json" in str(r.headers.get("Content-Type", "")).lower() else {}
        data = obj.get("data") if isinstance(obj, dict) else []
        out: list[str] = []
        if isinstance(data, list):
            for item in data:
                if isinstance(item, dict) and str(item.get("id") or "").strip():
                    out.append(str(item.get("id")).strip())
                elif isinstance(item, str) and item.strip():
                    out.append(item.strip())
        return (sorted(set(out)), "")
    except Exception as e:
        return ([], str(e))


def _llm_timeout_s(cfg: dict[str, Any] | None = None, default: int = 45) -> int:
    source = cfg or {}
    raw = source.get("LLM_TIMEOUT_S") if isinstance(source, dict) else default
    try:
        timeout_s = int(str(raw))
    except Exception:
        timeout_s = int(default)
    return max(5, min(600, timeout_s))


def _llm_max_tokens(cfg: dict[str, Any] | None, key: str, default: int) -> int:
    source = cfg or {}
    raw = source.get(str(key or ""), default) if isinstance(source, dict) else default
    try:
        value = int(str(raw))
    except Exception:
        value = int(default)
    return max(16, min(8192, value))


def _provider_chat_json(
    base_url: str,
    api_key: str,
    model: str,
    messages: list[dict[str, Any]],
    *,
    temperature: float = 0.0,
    max_tokens: int = 600,
    timeout_s: int = 45,
) -> dict[str, Any]:
    base = _provider_v1_base(base_url)
    if not base:
        raise RuntimeError("provider base not configured")
    headers = {"Content-Type": "application/json"}
    if str(api_key or "").strip():
        headers["Authorization"] = f"Bearer {str(api_key).strip()}"
    payload = {
        "model": str(model or "").strip(),
        "messages": messages,
        "temperature": float(temperature),
        "max_tokens": int(max_tokens),
    }
    r = requests.post(f"{base}/chat/completions", headers=headers, json=payload, timeout=max(5, int(timeout_s)))
    if r.status_code >= 400:
        raise RuntimeError(f"chat HTTP {r.status_code}: {r.text[:1200]}")
    return r.json() if "application/json" in str(r.headers.get("Content-Type", "")).lower() else {}


def _provider_embedding(base_url: str, api_key: str, model: str, text: str, *, timeout_s: int = 45) -> list[float]:
    base = _provider_v1_base(base_url)
    if not base:
        raise RuntimeError("embedding base not configured")
    headers = {"Content-Type": "application/json"}
    if str(api_key or "").strip():
        headers["Authorization"] = f"Bearer {str(api_key).strip()}"
    payload = {"model": str(model or "").strip(), "input": str(text or "")}
    r = requests.post(f"{base}/embeddings", headers=headers, json=payload, timeout=max(5, int(timeout_s)))
    if r.status_code >= 400:
        raise RuntimeError(f"emb HTTP {r.status_code}: {r.text[:1200]}")
    obj = r.json() if "application/json" in str(r.headers.get("Content-Type", "")).lower() else {}
    data = obj.get("data") if isinstance(obj, dict) else []
    if not isinstance(data, list) or not data:
        return []
    emb = (data[0] or {}).get("embedding") if isinstance(data[0], dict) else []
    if not isinstance(emb, list):
        return []
    out: list[float] = []
    for x in emb:
        try:
            out.append(float(x))
        except Exception:
            continue
    return out


def _provider_chat_stream_chunks(
    base_url: str,
    api_key: str,
    model: str,
    messages: list[dict[str, Any]],
    *,
    temperature: float = 0.4,
    max_tokens: int = 900,
    timeout_s: int = 300,
):
    base = _provider_v1_base(base_url)
    if not base:
        raise RuntimeError("provider base not configured")
    headers = {"Content-Type": "application/json"}
    if str(api_key or "").strip():
        headers["Authorization"] = f"Bearer {str(api_key).strip()}"
    payload = {
        "model": str(model or "").strip(),
        "messages": messages,
        "temperature": float(temperature),
        "max_tokens": int(max_tokens),
        "stream": True,
    }
    with requests.post(
        f"{base}/chat/completions",
        headers=headers,
        json=payload,
        timeout=(10, max(60, int(timeout_s))),
        stream=True,
    ) as r:
        if r.status_code >= 400:
            raise RuntimeError(f"chat HTTP {r.status_code}: {r.text[:1200]}")
        for raw_line in r.iter_lines(decode_unicode=False):
            try:
                line = raw_line.decode("utf-8", errors="replace") if isinstance(raw_line, (bytes, bytearray)) else str(raw_line or "")
            except Exception:
                line = str(raw_line or "")
            if not line:
                continue
            s = str(line).strip()
            if not s.startswith("data:"):
                continue
            data = s[5:].strip()
            if data == "[DONE]":
                break
            try:
                obj = json.loads(data)
            except Exception:
                continue
            choice = ((obj.get("choices") or [{}])[0] or {})
            delta = (choice.get("delta") or {}).get("content")
            if delta:
                yield str(delta)


def _extract_tags_by_llm(query: str, cfg: dict[str, Any], allowed_tags: list[str]) -> list[str]:
    q = str(query or "").strip()
    if not q or not allowed_tags:
        return []
    base = str(cfg.get("LLM_API_BASE") or "").strip()
    model = str(cfg.get("LLM_MODEL_CUSTOM") or cfg.get("LLM_MODEL") or "").strip()
    key = str(cfg.get("LLM_API_KEY") or "").strip()
    if not base or not model:
        return []
    system = str(cfg.get("PROMPT_TAG_EXTRACT_SYSTEM") or "").strip() or "Extract tags as JSON"
    user = (
        "用户查询(query):\n"
        + q
        + "\n\nallowed_tags(JSON array):\n"
        + json.dumps(list(allowed_tags)[:1200], ensure_ascii=False)
        + "\n\n只输出JSON: {\"tags\": [...]}"
    )
    obj = _provider_chat_json(
        base,
        key,
        model,
        [{"role": "system", "content": system}, {"role": "user", "content": user}],
        temperature=0.0,
        max_tokens=_llm_max_tokens(cfg, "LLM_MAX_TOKENS_TAG_EXTRACT", 1200),
        timeout_s=_llm_timeout_s(cfg),
    )
    text = ""
    try:
        text = str((((obj.get("choices") or [{}])[0] or {}).get("message") or {}).get("content") or "")
    except Exception:
        text = ""
    m = re.search(r"\{[\s\S]*\}", text)
    raw = m.group(0) if m else text
    try:
        data = json.loads(raw)
    except Exception:
        return []
    tags = data.get("tags") if isinstance(data, dict) else []
    if not isinstance(tags, list):
        return []
    return [str(x).strip() for x in tags if str(x).strip()]
