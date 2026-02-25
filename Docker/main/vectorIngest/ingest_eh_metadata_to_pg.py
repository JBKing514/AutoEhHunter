#!/usr/bin/env python3
"""Fetch E-Hentai metadata + cover images and upsert into PostgreSQL.

Features:
- Calls EH API (`gdata`) in batches
- Downloads gallery cover and stores SigLIP vector in `eh_works.cover_embedding`
- Loads EhTagTranslation db.text.js/json and translates tags
- Translation file is refreshed daily by default (24h cache)

Example:
  python ingest_eh_metadata_to_pg.py \
    --dsn "postgresql://user:pass@127.0.0.1:5432/lrr" \
    --gallery-url "https://e-hentai.org/g/123456/abcdef1234/" \
    --init-schema --schema ../textIngest/schema.sql
"""

from __future__ import annotations

import argparse
import base64
import datetime as dt
import html
import json
import re
import sys
import time
import os
from io import BytesIO
from pathlib import Path
from typing import Any, TypeVar

import requests


DEFAULT_TRANSLATION_URL = (
    "https://github.com/EhTagTranslation/Database/releases/latest/download/"
    "db.text.json"
)
DEFAULT_API_URL = "https://api.e-hentai.org/api.php"
GALLERY_RE = re.compile(r"https?://((?:e-hentai|exhentai)\.org)/g/(\d+)/([0-9A-Za-z]+)/?")


def _get_config_cipher_key() -> bytes | None:
    key_env = os.getenv("DATA_UI_CONFIG_CRYPT_KEY", "").strip()
    if key_env:
        if len(key_env) == 44 and key_env.endswith("="):
            return key_env.encode("ascii")
        return base64.urlsafe_b64encode(key_env.encode("utf-8")[:32].ljust(32, b"0"))

    candidates = [Path("/app/runtime/webui/.app_config.key"), Path("/app/runtime/.app_config.key")]
    for p in candidates:
        if p.exists():
            try:
                return p.read_bytes().strip()
            except Exception:
                continue
    return None


def _decrypt_secret_if_needed(value: str) -> str:
    s = str(value or "").strip()
    if not s.startswith("enc:v1:"):
        return s
    key = _get_config_cipher_key()
    if not key:
        return ""
    try:
        from cryptography.fernet import Fernet

        token = s[len("enc:v1:") :]
        return Fernet(key).decrypt(token.encode("utf-8")).decode("utf-8")
    except Exception:
        return ""


def _load_runtime_config_from_db(dsn: str) -> dict[str, str]:
    s = str(dsn or "").strip()
    if not s:
        return {}
    try:
        import importlib

        psycopg = importlib.import_module("psycopg")
    except Exception:
        return {}

    out: dict[str, str] = {}
    sql = "SELECT key, value, is_secret FROM app_config WHERE scope = %s"
    try:
        with psycopg.connect(s) as conn:
            with conn.cursor() as cur:
                cur.execute(sql, ("global",))
                for key, value, is_secret in cur.fetchall():
                    k = str(key)
                    v = str(value or "")
                    out[k] = _decrypt_secret_if_needed(v) if bool(is_secret) else v
    except Exception:
        return {}
    return out


def _split_csv(raw: str) -> list[str]:
    out: list[str] = []
    for item in str(raw or "").split(","):
        s = item.strip()
        if s:
            out.append(s)
    return out


def _load_schema_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _iter_gallery_urls(args: argparse.Namespace) -> list[str]:
    out: list[str] = []
    for u in args.gallery_url or []:
        s = (u or "").strip()
        if s:
            out.append(s)

    if args.gallery_file:
        p = Path(args.gallery_file)
        if not p.exists():
            raise RuntimeError(f"Gallery file not found: {p}")
        for line in p.read_text(encoding="utf-8").splitlines():
            s = line.strip()
            if not s or s.startswith("#"):
                continue
            out.append(s)

    seen: set[str] = set()
    dedup: list[str] = []
    for u in out:
        if u in seen:
            continue
        seen.add(u)
        dedup.append(u)
    return dedup


def _validate_simple_ident(name: str, default: str = "eh_queue") -> str:
    s = (name or "").strip()
    if not s:
        s = default
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", s):
        raise RuntimeError(f"Invalid table identifier: {name}")
    return s


def _dequeue_pending_urls(dsn: str, table: str, limit: int) -> list[str]:
    table = _validate_simple_ident(table)
    limit = max(1, int(limit))
    sql = (
        f"WITH picked AS ("
        f"  SELECT id, eh_url FROM {table} "
        f"  WHERE status = 'pending' "
        f"     OR (status = 'in_progress' AND locked_at IS NOT NULL AND locked_at < now() - interval '30 minutes') "
        f"  ORDER BY id "
        f"  LIMIT %s "
        f"  FOR UPDATE SKIP LOCKED"
        f") "
        f"UPDATE {table} q "
        f"SET status = 'in_progress', updated_at = now(), locked_at = now(), attempts = q.attempts + 1 "
        f"FROM picked p "
        f"WHERE q.id = p.id "
        f"RETURNING p.eh_url"
    )
    try:
        import importlib

        psycopg = importlib.import_module("psycopg")
    except Exception as e:
        raise RuntimeError('Missing dependency psycopg. Install with: pip install "psycopg[binary]"') from e

    out: list[str] = []
    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (limit,))
            rows = cur.fetchall()
            out = [str(r[0]).strip() for r in rows if r and str(r[0]).strip()]
        conn.commit()
    return out


def _complete_queue_rows(dsn: str, table: str, keys: set[tuple[int, str]], result: str) -> int:
    if not keys:
        return 0
    table = _validate_simple_ident(table)
    vals = list(keys)
    sql = (
        f"UPDATE {table} q "
        f"SET status = 'complete', result = %s, completed_at = now(), updated_at = now() "
        f"WHERE EXISTS ("
        f"  SELECT 1 FROM (VALUES "
        + ",".join(["(%s,%s)"] * len(vals))
        + f") AS v(gid, token) "
        f"  WHERE q.gid = v.gid AND q.token = v.token"
        f")"
    )
    params: list[Any] = [result]
    for gid, token in vals:
        params.extend([gid, token])

    try:
        import importlib

        psycopg = importlib.import_module("psycopg")
    except Exception as e:
        raise RuntimeError('Missing dependency psycopg. Install with: pip install "psycopg[binary]"') from e

    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            updated = int(cur.rowcount or 0)
        conn.commit()
    return updated


def _set_queue_rows_pending(dsn: str, table: str, keys: set[tuple[int, str]]) -> int:
    if not keys:
        return 0
    table = _validate_simple_ident(table)
    vals = list(keys)
    sql = (
        f"UPDATE {table} q "
        f"SET status = 'pending', result = NULL, updated_at = now(), locked_at = NULL "
        f"WHERE EXISTS ("
        f"  SELECT 1 FROM (VALUES "
        + ",".join(["(%s,%s)"] * len(vals))
        + f") AS v(gid, token) "
        f"  WHERE q.gid = v.gid AND q.token = v.token"
        f")"
    )
    params: list[Any] = []
    for gid, token in vals:
        params.extend([gid, token])

    try:
        import importlib

        psycopg = importlib.import_module("psycopg")
    except Exception as e:
        raise RuntimeError('Missing dependency psycopg. Install with: pip install "psycopg[binary]"') from e

    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            updated = int(cur.rowcount or 0)
        conn.commit()
    return updated


def _cleanup_completed_queue_rows(dsn: str, table: str) -> int:
    table = _validate_simple_ident(table)
    sql = f"DELETE FROM {table} WHERE status = 'complete'"
    try:
        import importlib

        psycopg = importlib.import_module("psycopg")
    except Exception as e:
        raise RuntimeError('Missing dependency psycopg. Install with: pip install "psycopg[binary]"') from e

    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute(sql)
            removed = int(cur.rowcount or 0)
        conn.commit()
    return removed


def _remove_ingested_urls_from_queue(queue_file: Path, succeeded_keys: set[tuple[int, str]]) -> int:
    if not queue_file.exists() or not succeeded_keys:
        return 0

    kept: list[str] = []
    removed = 0

    for line in queue_file.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            kept.append(line)
            continue
        try:
            gid, token, _ = _parse_gallery_url(s)
            if (gid, token) in succeeded_keys:
                removed += 1
                continue
        except Exception:
            # Keep invalid lines untouched; user may want to inspect/fix manually.
            pass
        kept.append(line)

    queue_file.write_text("\n".join(kept).rstrip() + "\n", encoding="utf-8")
    return removed


def _parse_gallery_url(url: str) -> tuple[int, str, str]:
    m = GALLERY_RE.search(url.strip())
    if not m:
        raise RuntimeError(f"Invalid EH gallery URL: {url}")
    host = m.group(1).lower()
    gid = int(m.group(2))
    token = m.group(3)
    normalized = f"https://{host}/g/{gid}/{token}/"
    return gid, token, normalized


T = TypeVar("T")


def _chunks(items: list[T], n: int) -> list[list[T]]:
    return [items[i : i + n] for i in range(0, len(items), n)]


def _download_translation_payload(
    session: requests.Session,
    url: str,
    cache_path: Path,
    max_age_hours: int,
    force_refresh: bool,
    timeout_s: int,
) -> str:
    use_cache = False
    if cache_path.exists() and not force_refresh:
        mtime = dt.datetime.fromtimestamp(cache_path.stat().st_mtime, tz=dt.timezone.utc)
        age = dt.datetime.now(tz=dt.timezone.utc) - mtime
        if age <= dt.timedelta(hours=max_age_hours):
            use_cache = True

    if use_cache:
        return cache_path.read_text(encoding="utf-8")

    def _candidate_urls(primary: str) -> list[str]:
        cands = [primary]
        latest_json = "https://github.com/EhTagTranslation/Database/releases/latest/download/db.text.json"
        latest_js = "https://github.com/EhTagTranslation/Database/releases/latest/download/db.text.js"
        cands.extend([latest_json, latest_js])
        # If user passed a pinned version URL, also try replacing it with latest.
        replaced = re.sub(
            r"/releases/download/[^/]+/db\.text\.(?:js|json)$",
            "/releases/latest/download/db.text.json",
            primary,
        )
        if replaced != primary:
            cands.append(replaced)
        # De-dup while preserving order.
        out: list[str] = []
        seen: set[str] = set()
        for u in cands:
            if u in seen:
                continue
            seen.add(u)
            out.append(u)
        return out

    last_err: Exception | None = None
    for candidate in _candidate_urls(url):
        try:
            r = session.get(candidate, timeout=timeout_s)
            r.raise_for_status()
            txt = r.text
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            cache_path.write_text(txt, encoding="utf-8")
            return txt
        except requests.HTTPError as e:
            last_err = e
            resp = getattr(e, "response", None)
            if resp is not None and int(resp.status_code) == 404:
                continue
            raise

    if last_err is not None:
        raise last_err
    raise RuntimeError("Failed to download translation payload")


def _parse_translation_json(text: str) -> dict[str, Any]:
    # Some releases are pure JSON; some are JS wrappers. Try both.
    try:
        obj = json.loads(text)
        if isinstance(obj, dict):
            return obj
    except Exception:
        pass

    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        obj = json.loads(text[start : end + 1])
        if isinstance(obj, dict):
            return obj

    raise RuntimeError("Failed to parse translation db.text payload")


def _build_translation_maps(payload: dict[str, Any]) -> tuple[dict[str, str], dict[str, dict[str, str]], str | None]:
    namespace_map: dict[str, str] = {}
    tag_map: dict[str, dict[str, str]] = {}
    head_sha = None

    head = payload.get("head")
    if isinstance(head, dict):
        sha = head.get("sha")
        if isinstance(sha, str) and sha.strip():
            head_sha = sha.strip()

    rows = payload.get("data")
    if not isinstance(rows, list):
        return namespace_map, tag_map, head_sha

    for row in rows:
        if not isinstance(row, dict):
            continue
        ns = row.get("namespace")
        data = row.get("data")
        if not isinstance(ns, str) or not isinstance(data, dict):
            continue

        if ns == "rows":
            for raw_ns, detail in data.items():
                if isinstance(raw_ns, str) and isinstance(detail, dict):
                    name = detail.get("name")
                    if isinstance(name, str) and name.strip():
                        namespace_map[raw_ns] = name.strip()
            continue

        ns_tags: dict[str, str] = {}
        for raw_tag, detail in data.items():
            if not isinstance(raw_tag, str):
                continue
            translated = None
            if isinstance(detail, dict):
                name = detail.get("name")
                if isinstance(name, str) and name.strip():
                    translated = name.strip()
            elif isinstance(detail, str) and detail.strip():
                translated = detail.strip()
            if translated:
                ns_tags[raw_tag] = translated

        if ns_tags:
            tag_map[ns] = ns_tags

    return namespace_map, tag_map, head_sha


def _translate_tag(raw_tag: str, namespace_map: dict[str, str], tag_map: dict[str, dict[str, str]]) -> str:
    s = raw_tag.strip()
    if not s:
        return s
    if ":" not in s:
        return s

    ns, val = s.split(":", 1)
    ns = ns.strip()
    val = val.strip()
    if not ns or not val:
        return s

    t_ns = namespace_map.get(ns, ns)
    t_val = tag_map.get(ns, {}).get(val, val)
    return f"{t_ns}:{t_val}"


def _vector_literal(vec: list[float]) -> str:
    return "[" + ",".join(repr(float(x)) for x in vec) + "]"


class SiglipClient:
    def __init__(self, base_url: str, timeout_s: int = 120):
        self.base_url = base_url.rstrip("/")
        self.timeout_s = timeout_s

    def embed_image_bytes(self, image_bytes: bytes) -> list[float]:
        import base64
        b64 = base64.b64encode(image_bytes).decode("ascii")
        r = requests.post(
            f"{self.base_url}/api/internal/embed/image",
            json={"image": b64},
            timeout=self.timeout_s,
        )
        r.raise_for_status()
        obj = r.json()
        emb = obj.get("embedding")
        if not isinstance(emb, list):
            raise RuntimeError(f"Invalid embedding response: {obj}")
        return [float(x) for x in emb]


def _fetch_cover_bytes(
    session: requests.Session,
    thumb_url: str,
    referer: str,
    timeout_s: int,
) -> bytes | None:
    if not thumb_url:
        return None

    headers = {"Referer": referer}
    r = session.get(thumb_url, headers=headers, timeout=timeout_s)
    r.raise_for_status()
    return r.content


def _as_int_or_none(v: Any) -> int | None:
    if v is None:
        return None
    s = str(v).strip()
    if not s:
        return None
    if s.isdigit():
        return int(s)
    return None


def _as_float_or_none(v: Any) -> float | None:
    if v is None:
        return None
    s = str(v).strip()
    if not s:
        return None
    try:
        return float(s)
    except Exception:
        return None


def _parse_filter_values(items: list[str] | None) -> set[str]:
    out: set[str] = set()
    for raw in items or []:
        if raw is None:
            continue
        for part in str(raw).split(","):
            s = part.strip().lower()
            if s:
                out.add(s)
    return out


def _has_blocked_tag(tags_raw: list[str], tags_translated: list[str], blocked_tags: set[str]) -> bool:
    if not blocked_tags:
        return False

    def _match_list(tags: list[str]) -> bool:
        for t in tags:
            s = str(t or "").strip().lower()
            if not s:
                continue
            if s in blocked_tags:
                return True
            if ":" in s:
                _, val = s.split(":", 1)
                if val in blocked_tags:
                    return True
        return False

    # Match either original tags or translated tags.
    if _match_list(tags_raw):
        return True
    if _match_list(tags_translated):
        return True
    return False


def _eh_gdata(
    session: requests.Session,
    api_url: str,
    gidlist: list[tuple[int, str]],
    timeout_s: int,
    sleep_s: float = 0.0,
) -> list[dict[str, Any]]:
    if sleep_s > 0:
        time.sleep(sleep_s)
    payload = {
        "method": "gdata",
        "gidlist": [[gid, token] for gid, token in gidlist],
        "namespace": 1,
    }
    r = session.post(api_url, json=payload, timeout=timeout_s)
    r.raise_for_status()
    obj = r.json()
    if isinstance(obj, dict) and obj.get("error"):
        raise RuntimeError(f"EH API error: {obj.get('error')}")
    rows = obj.get("gmetadata") if isinstance(obj, dict) else None
    if not isinstance(rows, list):
        raise RuntimeError("Unexpected EH API response: gmetadata missing")
    return [x for x in rows if isinstance(x, dict)]


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="Fetch EH metadata + covers and upsert into eh_works")
    ap.add_argument("--dsn", required=True, help="PostgreSQL DSN")
    ap.add_argument("--api-url", default=DEFAULT_API_URL, help="EH API URL")
    ap.add_argument("--gallery-url", action="append", help="EH gallery URL (repeatable)")
    ap.add_argument("--gallery-file", help="Text file containing gallery URLs (one per line)")
    ap.add_argument("--queue-table", default=os.getenv("EH_QUEUE_TABLE", "eh_queue"), help="PostgreSQL queue table (default: eh_queue)")
    ap.add_argument("--queue-limit", type=int, default=int(os.getenv("EH_QUEUE_LIMIT", "2000")), help="Max pending URLs to dequeue per run")
    ap.add_argument(
        "--queue-file",
        help=(
            "[deprecated] Queue file path for incremental ingestion. "
            "Prefer --queue-table."
        ),
    )
    ap.add_argument("--api-batch-size", type=int, default=25, help="EH API gidlist batch size")
    ap.add_argument("--timeout", type=int, default=45, help="HTTP timeout seconds")
    ap.add_argument("--sleep-seconds", type=float, default=4.0, help="Sleep seconds between EH requests")
    ap.add_argument("--cookie", default="", help="Optional Cookie header for EH/EX access")
    ap.add_argument("--user-agent", default="AutoEhHunter/1.0", help="HTTP User-Agent")
    ap.add_argument(
        "--siglip-base",
        default=os.getenv("WEBAPI_BASE", "http://localhost:8501"),
        help="Base URL for image embedding API (default: http://localhost:8501)",
    )

    ap.add_argument(
        "--category",
        "--exclude-category",
        action="append",
        dest="exclude_category",
        default=[],
        help=(
            "Exclude category from ingest (repeatable or comma-separated). "
            "Example: --category manga --category western"
        ),
    )
    ap.add_argument(
        "--rating",
        "--min-rating",
        type=float,
        dest="min_rating",
        default=None,
        help="Minimum rating required to ingest (rows with missing rating are filtered)",
    )
    ap.add_argument(
        "--tag",
        "--exclude-tag",
        action="append",
        dest="exclude_tag",
        default=[],
        help=(
            "Exclude tag from ingest (repeatable or comma-separated). "
            "Matches full tag or value part after namespace, case-insensitive. "
            "Example: --tag lolicon --tag female:rape"
        ),
    )

    ap.add_argument("--translation-url", default=DEFAULT_TRANSLATION_URL, help="EhTagTranslation db.text URL")
    ap.add_argument(
        "--translation-cache",
        default=str(Path(__file__).resolve().parent / "cache" / "db.text.js"),
        help="Local cache path for translation payload",
    )
    ap.add_argument("--translation-max-age-hours", type=int, default=24, help="Refresh translation cache after this age")
    ap.add_argument("--force-refresh-translation", action="store_true", help="Force download translation now")

    ap.add_argument(
        "--schema",
        default=str(Path(__file__).resolve().parents[1] / "textIngest" / "schema.sql"),
        help="Path to schema.sql",
    )
    ap.add_argument("--init-schema", action="store_true", help="Initialize schema before ingest")
    ap.add_argument("--dry-run", action="store_true", help="Parse/fetch only, do not write database")
    args = ap.parse_args(argv)

    db_cfg = _load_runtime_config_from_db(args.dsn)
    if db_cfg:
        if (not args.exclude_category) and str(db_cfg.get("EH_FILTER_CATEGORY", "")).strip():
            args.exclude_category = _split_csv(db_cfg.get("EH_FILTER_CATEGORY", ""))
        if args.min_rating is None and str(db_cfg.get("EH_MIN_RATING", "")).strip():
            try:
                args.min_rating = float(str(db_cfg.get("EH_MIN_RATING", "")).strip())
            except Exception:
                args.min_rating = None
        if (not args.exclude_tag) and str(db_cfg.get("EH_FILTER_TAG", "")).strip():
            args.exclude_tag = _split_csv(db_cfg.get("EH_FILTER_TAG", ""))
        if not str(args.cookie or "").strip() and str(db_cfg.get("EH_COOKIE", "")).strip():
            args.cookie = str(db_cfg.get("EH_COOKIE", "")).strip()
        if args.user_agent == "AutoEhHunter/1.0" and str(db_cfg.get("EH_USER_AGENT", "")).strip():
            args.user_agent = str(db_cfg.get("EH_USER_AGENT", "")).strip()
        if args.api_url == DEFAULT_API_URL and str(db_cfg.get("EH_API_URL", "")).strip():
            args.api_url = str(db_cfg.get("EH_API_URL", "")).strip()

    if args.queue_file and not args.gallery_file:
        args.gallery_file = args.queue_file

    urls = _iter_gallery_urls(args)
    used_queue_table = False
    if not urls:
        urls = _dequeue_pending_urls(args.dsn, args.queue_table, args.queue_limit)
        used_queue_table = True
    if not urls:
        print("No gallery URLs provided. Queue table has no pending rows.", file=sys.stderr)
        return 2

    parsed_urls: list[tuple[int, str, str]] = []
    for u in urls:
        parsed_urls.append(_parse_gallery_url(u))
    dequeued_keys: set[tuple[int, str]] = {(gid, token) for gid, token, _ in parsed_urls}

    # Keep first URL for each (gid, token) pair.
    url_map: dict[tuple[int, str], str] = {}
    for gid, token, normalized in parsed_urls:
        url_map.setdefault((gid, token), normalized)

    session = requests.Session()
    session.headers.update({"User-Agent": args.user_agent})
    if args.cookie.strip():
        session.headers.update({"Cookie": args.cookie.strip()})

    cache_path = Path(args.translation_cache)
    translation_text = _download_translation_payload(
        session=session,
        url=args.translation_url,
        cache_path=cache_path,
        max_age_hours=max(1, int(args.translation_max_age_hours)),
        force_refresh=bool(args.force_refresh_translation),
        timeout_s=args.timeout,
    )
    translation_payload = _parse_translation_json(translation_text)
    namespace_map, tag_map, translation_head_sha = _build_translation_maps(translation_payload)

    gid_pairs = list(url_map.keys())
    all_meta: list[dict[str, Any]] = []
    sleep_s = max(0.0, float(args.sleep_seconds))
    for batch in _chunks(gid_pairs, max(1, int(args.api_batch_size))):
        all_meta.extend(_eh_gdata(session, args.api_url, batch, timeout_s=args.timeout, sleep_s=sleep_s))

    blocked_categories = _parse_filter_values(args.exclude_category)
    blocked_tags = _parse_filter_values(args.exclude_tag)
    min_rating = args.min_rating if args.min_rating is None else float(args.min_rating)

    siglip = SiglipClient(base_url=str(args.siglip_base), timeout_s=args.timeout)

    rows_to_upsert: list[tuple[Any, ...]] = []
    succeeded_keys: set[tuple[int, str]] = set()
    filtered_keys: set[tuple[int, str]] = set()
    filtered_category = 0
    filtered_rating = 0
    filtered_tag = 0
    processed = 0
    cover_ok = 0

    for meta in all_meta:
        try:
            gid = _as_int_or_none(meta.get("gid"))
            if gid is None:
                continue
            token = str(meta.get("token") or "").strip()
            if not token:
                continue

            eh_url = f"https://e-hentai.org/g/{gid}/{token}/"
            ex_url = f"https://exhentai.org/g/{gid}/{token}/"
            source_url = url_map.get((gid, token), eh_url)
            tags_raw = [str(t).strip() for t in (meta.get("tags") or []) if str(t).strip()]
            tags_translated = [_translate_tag(t, namespace_map, tag_map) for t in tags_raw]

            title = html.unescape(str(meta.get("title") or ""))
            title_jpn = html.unescape(str(meta.get("title_jpn") or ""))
            category = str(meta.get("category") or "").strip().lower() or None
            rating = _as_float_or_none(meta.get("rating"))
            posted = _as_int_or_none(meta.get("posted"))
            uploader = str(meta.get("uploader") or "").strip() or None
            filecount = _as_int_or_none(meta.get("filecount"))

            if blocked_categories and category and category in blocked_categories:
                filtered_category += 1
                filtered_keys.add((gid, token))
                continue

            if blocked_tags and _has_blocked_tag(tags_raw, tags_translated, blocked_tags):
                filtered_tag += 1
                filtered_keys.add((gid, token))
                continue

            if min_rating is not None and (rating is None or rating < min_rating):
                filtered_rating += 1
                filtered_keys.add((gid, token))
                continue

            cover_vec: list[float] | None = None
            thumb = str(meta.get("thumb") or "").strip()
            if thumb:
                try:
                    if sleep_s > 0:
                        time.sleep(sleep_s)
                    cover_bytes = _fetch_cover_bytes(
                        session=session,
                        thumb_url=thumb,
                        referer=source_url,
                        timeout_s=args.timeout,
                    )
                    if cover_bytes:
                        cover_vec = siglip.embed_image_bytes(cover_bytes)
                        cover_ok += 1
                except Exception as e:
                    print(f"WARN cover fetch failed gid={gid}: {e}", file=sys.stderr)

            raw_json = json.dumps(meta, ensure_ascii=False)
            rows_to_upsert.append(
                (
                    gid,
                    token,
                    eh_url,
                    ex_url,
                    title,
                    title_jpn,
                    category,
                    tags_raw,
                    tags_translated,
                    _vector_literal(cover_vec) if cover_vec else None,
                    posted,
                    uploader,
                    filecount,
                    args.translation_url,
                    translation_head_sha,
                    raw_json,
                )
            )
            succeeded_keys.add((gid, token))
            processed += 1
        except Exception as e:
            print(f"WARN skip invalid metadata row: {e}", file=sys.stderr)

    print(
        f"Fetched metadata rows={len(all_meta)}, processed={processed}, "
        f"filtered_total={filtered_category + filtered_rating + filtered_tag}, "
        f"filtered(category={filtered_category},rating={filtered_rating},tag={filtered_tag}), "
        f"cover_ok={cover_ok}, translation_sha={translation_head_sha or 'unknown'}",
        file=sys.stderr,
    )

    if args.dry_run:
        print("Dry run enabled: no DB writes.", file=sys.stderr)
        if used_queue_table and dequeued_keys:
            reset = _set_queue_rows_pending(args.dsn, args.queue_table, dequeued_keys)
            print(f"Queue reset(db): pending={reset}, table={args.queue_table}", file=sys.stderr)
        return 0

    try:
        import importlib

        psycopg = importlib.import_module("psycopg")
    except Exception as e:
        print('Missing dependency psycopg. Install with: pip install "psycopg[binary]"', file=sys.stderr)
        print(str(e), file=sys.stderr)
        return 2

    upsert_sql = (
        "INSERT INTO eh_works ("
        "gid, token, eh_url, ex_url, title, title_jpn, category, tags, tags_translated, "
        "cover_embedding, posted, uploader, filecount, "
        "translation_repo_url, translation_head_sha, raw, last_fetched_at, updated_at"
        ") VALUES ("
        "%s, %s, %s, %s, %s, %s, %s, %s, %s, %s::vector, %s, %s, %s, %s, %s, %s::jsonb, now(), now()"
        ") ON CONFLICT (gid, token) DO UPDATE SET "
        "eh_url = EXCLUDED.eh_url, "
        "ex_url = EXCLUDED.ex_url, "
        "title = EXCLUDED.title, "
        "title_jpn = EXCLUDED.title_jpn, "
        "category = EXCLUDED.category, "
        "tags = EXCLUDED.tags, "
        "tags_translated = EXCLUDED.tags_translated, "
        "cover_embedding = COALESCE(EXCLUDED.cover_embedding, eh_works.cover_embedding), "
        "posted = EXCLUDED.posted, "
        "uploader = EXCLUDED.uploader, "
        "filecount = EXCLUDED.filecount, "
        "translation_repo_url = EXCLUDED.translation_repo_url, "
        "translation_head_sha = EXCLUDED.translation_head_sha, "
        "raw = EXCLUDED.raw, "
        "last_fetched_at = now(), "
        "updated_at = now()"
    )

    with psycopg.connect(args.dsn) as conn:
        conn.execute("SET statement_timeout = '10min'")

        if args.init_schema:
            schema_sql = _load_schema_text(Path(args.schema))
            with conn.cursor() as cur:
                cur.execute(schema_sql)
            conn.commit()

        if rows_to_upsert:
            with conn.cursor() as cur:
                cur.executemany(upsert_sql, rows_to_upsert)
            conn.commit()

    if used_queue_table:
        ingested_done = _complete_queue_rows(args.dsn, args.queue_table, succeeded_keys, "ingested")
        filtered_done = _complete_queue_rows(args.dsn, args.queue_table, filtered_keys, "filtered")
        other_keys = dequeued_keys - succeeded_keys - filtered_keys
        other_done = _complete_queue_rows(args.dsn, args.queue_table, other_keys, "skipped")
        removed = _cleanup_completed_queue_rows(args.dsn, args.queue_table)
        print(
            f"Queue cleanup(db): completed_ingested={ingested_done}, completed_filtered={filtered_done}, completed_skipped={other_done}, "
            f"deleted_complete={removed}, table={args.queue_table}",
            file=sys.stderr,
        )
    elif args.queue_file:
        cleanup_keys = succeeded_keys | filtered_keys
        removed = _remove_ingested_urls_from_queue(Path(args.queue_file), cleanup_keys)
        print(
            f"Queue cleanup(file): removed={removed} from {args.queue_file} "
            f"(ingested={len(succeeded_keys)}, filtered={len(filtered_keys)})",
            file=sys.stderr,
        )

    print(f"Done. Upserted rows={len(rows_to_upsert)}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
