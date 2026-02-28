import json
import sys
import threading
import time
import traceback
import base64
import urllib.parse
import random
from urllib.parse import parse_qs, unquote, urlparse
from typing import Any

import psycopg
import requests

from .config_service import resolve_config
from .db_service import db_dsn
from .vision_service import _embed_image_siglip


_worker_thread: threading.Thread | None = None
_worker_stop = threading.Event()
_worker_lock = threading.Lock()
_table_slot_cv = threading.Condition()
_active_table_name: str | None = None
_worker_status_lock = threading.Lock()
_worker_status: dict[str, Any] = {
    "running": False,
    "stopped_by_user": False,
    "table": "",
    "phase": "idle",
    "picked": 0,
    "completed": 0,
    "failed": 0,
    "current": 0,
    "total": 0,
    "updated_at": int(time.time()),
}


def _update_worker_status(**kwargs: Any) -> None:
    with _worker_status_lock:
        _worker_status.update(kwargs)
        _worker_status["updated_at"] = int(time.time())


def _read_worker_status() -> dict[str, Any]:
    with _worker_status_lock:
        return dict(_worker_status)


def _vector_literal(vec: list[float]) -> str:
    return "[" + ",".join(repr(float(x)) for x in vec) + "]"


def _l2_normalize(vec: list[float]) -> list[float]:
    if not vec:
        return []
    s = 0.0
    for x in vec:
        s += float(x) * float(x)
    if s <= 0.0:
        return []
    inv = s ** -0.5
    return [float(x) * inv for x in vec]


def _average_l2(vecs: list[list[float]]) -> list[float]:
    src = [list(v) for v in vecs if isinstance(v, list) and v]
    if not src:
        return []
    dim = len(src[0])
    arr = [v for v in src if len(v) == dim]
    if not arr:
        return []
    acc = [0.0] * dim
    for v in arr:
        for i in range(dim):
            acc[i] += float(v[i])
    acc = [x / float(len(arr)) for x in acc]
    return _l2_normalize(acc)


def _acquire_table_slot(name: str) -> None:
    global _active_table_name
    wanted = str(name or "").strip().lower()
    if not wanted:
        return
    with _table_slot_cv:
        while _active_table_name is not None:
            _table_slot_cv.wait(timeout=0.5)
        _active_table_name = wanted


def _release_table_slot(name: str) -> None:
    global _active_table_name
    wanted = str(name or "").strip().lower()
    with _table_slot_cv:
        if _active_table_name == wanted:
            _active_table_name = None
        _table_slot_cv.notify_all()


def _pick_candidates(conn: psycopg.Connection, include_fail: bool, limit: int) -> list[dict[str, Any]]:
    statuses = ["pending", "processing"]
    if include_fail:
        statuses.append("fail")
    sql = (
        "WITH picked AS ("
        "  SELECT gid, token, eh_url, ex_url, raw "
        "  FROM eh_works "
        "  WHERE cover_embedding IS NULL "
        "    AND cover_embedding_status = ANY(%s) "
        "  ORDER BY posted DESC NULLS LAST, updated_at DESC "
        "  LIMIT %s "
        "  FOR UPDATE SKIP LOCKED"
        ") "
        "UPDATE eh_works w "
        "SET cover_embedding_status = 'processing', updated_at = now() "
        "FROM picked p "
        "WHERE w.gid = p.gid AND w.token = p.token "
        "RETURNING p.gid, p.token, p.eh_url, p.ex_url, p.raw"
    )
    with conn.cursor() as cur:
        cur.execute(sql, (statuses, int(max(1, limit))))
        rows = cur.fetchall() or []
    out: list[dict[str, Any]] = []
    for row in rows:
        gid, token, eh_url, ex_url, raw = row
        payload = raw
        if isinstance(raw, str):
            try:
                payload = json.loads(raw)
            except Exception:
                payload = {}
        if not isinstance(payload, dict):
            payload = {}
        out.append(
            {
                "gid": int(gid),
                "token": str(token or ""),
                "eh_url": str(eh_url or ""),
                "ex_url": str(ex_url or ""),
                "raw": payload,
            }
        )
    return out


def _pick_work_candidates(conn: psycopg.Connection, include_fail: bool, limit: int) -> list[dict[str, Any]]:
    statuses = ["pending", "processing"]
    if include_fail:
        statuses.append("fail")
    sql = (
        "WITH picked AS ("
        "  SELECT arcid "
        "  FROM works "
        "  WHERE (visual_embedding IS NULL OR page_visual_embedding IS NULL) "
        "    AND cover_embedding_status = ANY(%s) "
        "  ORDER BY COALESCE(lastreadtime, date_added, eh_posted, 0) DESC, arcid DESC "
        "  LIMIT %s "
        "  FOR UPDATE SKIP LOCKED"
        ") "
        "UPDATE works w "
        "SET cover_embedding_status = 'processing' "
        "FROM picked p "
        "WHERE w.arcid = p.arcid "
        "RETURNING p.arcid"
    )
    with conn.cursor() as cur:
        cur.execute(sql, (statuses, int(max(1, limit))))
        rows = cur.fetchall() or []
    return [{"arcid": str(r[0] or "")} for r in rows if str(r[0] or "").strip()]


def _count_pending_eh(conn: psycopg.Connection) -> int:
    with conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM eh_works WHERE cover_embedding IS NULL")
        row = cur.fetchone() or [0]
    return int(row[0] or 0)


def _count_pending_works(conn: psycopg.Connection) -> int:
    with conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM works WHERE (visual_embedding IS NULL OR page_visual_embedding IS NULL)")
        row = cur.fetchone() or [0]
    return int(row[0] or 0)


def _fetch_cover_bytes(session: requests.Session, thumb_url: str, referer: str, timeout_s: int) -> bytes:
    base = str(thumb_url or "").strip()
    if not base:
        raise RuntimeError("thumb missing")

    candidates = [
        base,
        base.replace("https://ehgt.org/", "https://s.exhentai.org/"),
        base.replace("https://s.exhentai.org/", "https://ehgt.org/"),
    ]
    dedup: list[str] = []
    seen: set[str] = set()
    for u in candidates:
        if u and u not in seen:
            seen.add(u)
            dedup.append(u)

    last_err: Exception | None = None
    for attempt in range(3):
        for u in dedup:
            try:
                headers = {"Referer": str(referer or "")} if referer else {}
                resp = session.get(u, headers=headers, timeout=max(5, int(timeout_s)))
                resp.raise_for_status()
                return resp.content
            except Exception as e:
                last_err = e
                continue
        if attempt < 2:
            time.sleep(1.0 * (attempt + 1))
    raise RuntimeError(f"cover fetch failed after retries: {last_err}")


def _refresh_thumb_from_api(
    conn: psycopg.Connection,
    session: requests.Session,
    gid: int,
    token: str,
    timeout_s: int,
) -> tuple[str, str, str]:
    safe_token = str(token or "").strip()
    if gid <= 0 or not safe_token:
        return "", "", ""
    payload = {"method": "gdata", "gidlist": [[int(gid), safe_token]], "namespace": 1}
    try:
        r = session.post("https://api.e-hentai.org/api.php", json=payload, timeout=max(10, int(timeout_s)))
        r.raise_for_status()
        obj = r.json()
    except Exception:
        return "", "", ""
    rows = obj.get("gmetadata") if isinstance(obj, dict) else None
    if not isinstance(rows, list) or not rows:
        return "", "", ""
    row = rows[0] if isinstance(rows[0], dict) else None
    if not isinstance(row, dict):
        return "", "", ""
    new_thumb = str(row.get("thumb") or "").strip()
    if not new_thumb:
        return "", "", ""

    eh_url = f"https://e-hentai.org/g/{int(gid)}/{safe_token}/"
    ex_url = f"https://exhentai.org/g/{int(gid)}/{safe_token}/"
    with conn.cursor() as cur:
        cur.execute(
            "UPDATE eh_works "
            "SET raw = COALESCE(raw, '{}'::jsonb) || %s::jsonb, "
            "eh_url = %s, ex_url = %s, last_fetched_at = now(), updated_at = now() "
            "WHERE gid = %s AND token = %s "
            "RETURNING raw->>'thumb', eh_url, ex_url",
            (json.dumps(row, ensure_ascii=False), eh_url, ex_url, int(gid), safe_token),
        )
        got = cur.fetchone()
    if got:
        return str(got[0] or new_thumb), str(got[1] or eh_url), str(got[2] or ex_url)
    return new_thumb, eh_url, ex_url


def _mark_success(conn: psycopg.Connection, gid: int, token: str, vec: list[float]) -> None:
    with conn.cursor() as cur:
        cur.execute(
            "UPDATE eh_works "
            "SET cover_embedding = %s::vector, cover_embedding_status = 'complete', updated_at = now() "
            "WHERE gid = %s AND token = %s",
            (_vector_literal(vec), int(gid), str(token)),
        )


def _mark_fail(conn: psycopg.Connection, gid: int, token: str) -> None:
    with conn.cursor() as cur:
        cur.execute(
            "UPDATE eh_works "
            "SET cover_embedding_status = 'fail', updated_at = now() "
            "WHERE gid = %s AND token = %s",
            (int(gid), str(token)),
        )


def _mark_work_success(conn: psycopg.Connection, arcid: str, cover_vec: list[float], page_vec: list[float]) -> None:
    with conn.cursor() as cur:
        cur.execute(
            "UPDATE works "
            "SET visual_embedding = %s::vector, page_visual_embedding = %s::vector, cover_embedding_status = 'complete' "
            "WHERE arcid = %s",
            (_vector_literal(cover_vec), _vector_literal(page_vec), str(arcid)),
        )


def _mark_work_fail(conn: psycopg.Connection, arcid: str) -> None:
    with conn.cursor() as cur:
        cur.execute(
            "UPDATE works "
            "SET cover_embedding_status = 'fail' "
            "WHERE arcid = %s",
            (str(arcid),),
        )


def _lrr_request_headers(api_key: str) -> dict[str, str]:
    out: dict[str, str] = {"Accept": "*/*"}
    v = str(api_key or "").strip()
    if v:
        token = base64.b64encode(v.encode("utf-8")).decode("ascii")
        out["Authorization"] = f"Bearer {token}"
    return out


def _normalize_lrr_base(raw: str) -> str:
    s = str(raw or "").strip().rstrip("/")
    if not s:
        return ""
    if not s.startswith("http://") and not s.startswith("https://"):
        s = f"http://{s}"
    return s.rstrip("/")


def _fetch_lrr_thumb(session: requests.Session, lrr_base: str, arcid: str, api_key: str, timeout_s: int) -> bytes:
    a = urllib.parse.quote(str(arcid or "").strip(), safe="")
    if not a:
        raise RuntimeError("arcid missing")
    url = f"{lrr_base}/api/archives/{a}/thumbnail"
    r = session.get(url, headers=_lrr_request_headers(api_key), timeout=max(6, int(timeout_s)))
    r.raise_for_status()
    return r.content


def _lrr_get_archive_pages(session: requests.Session, lrr_base: str, arcid: str, api_key: str, timeout_s: int) -> list[str]:
    a = urllib.parse.quote(str(arcid or "").strip(), safe="")
    if not a:
        return []
    url = f"{lrr_base}/api/archives/{a}/files"
    r = session.get(url, headers={**_lrr_request_headers(api_key), "Accept": "application/json"}, timeout=max(6, int(timeout_s)))
    r.raise_for_status()
    obj = r.json()
    pages = obj.get("pages") if isinstance(obj, dict) else []
    out: list[str] = []
    for p in pages or []:
        if not isinstance(p, str):
            continue
        s = p.lstrip("./")
        out.append(f"{lrr_base}/{s}")
    return out


def _page_filename_from_url(page_url: str) -> str:
    try:
        parsed = urlparse(page_url)
        q = parse_qs(parsed.query)
        vals = q.get("path") or []
        if vals:
            return str(unquote(vals[0] or "")).split("/")[-1]
        return str(unquote(parsed.path or "")).split("/")[-1]
    except Exception:
        return ""


def _is_thumb_filename(filename: str) -> bool:
    n = str(filename or "").strip().lower()
    return bool(n.startswith(".thumb") or "path=.thumb" in n)


def _fetch_lrr_page_bytes(session: requests.Session, page_url: str, api_key: str, timeout_s: int) -> bytes:
    r = session.get(str(page_url or "").strip(), headers=_lrr_request_headers(api_key), timeout=max(6, int(timeout_s)))
    r.raise_for_status()
    return r.content


def _pick_lrr_page_urls(pages: list[str], rng: random.Random, inner_k: int = 4) -> tuple[str | None, list[str]]:
    non_thumb: list[str] = []
    for u in pages or []:
        fn = _page_filename_from_url(u)
        if not fn or _is_thumb_filename(fn):
            continue
        non_thumb.append(u)
    if not non_thumb:
        return None, []
    cover = non_thumb[0]
    others = [u for u in non_thumb if u != cover]
    if len(others) <= int(max(0, inner_k)):
        return cover, others
    return cover, rng.sample(others, k=int(max(0, inner_k)))


def run_eh_cover_embedding_once(*, include_fail: bool = False, limit: int = 12) -> dict[str, int]:
    cfg, _ = resolve_config()
    dsn = str(db_dsn() or "").strip()
    if not dsn:
        return {"picked": 0, "completed": 0, "failed": 0}

    sleep_s = max(0.0, float(cfg.get("EH_REQUEST_SLEEP", 4.0)))
    timeout_s = int(float(cfg.get("EH_REQUEST_SLEEP", 4.0)) * 8 + 20)
    model_id = str(cfg.get("SIGLIP_MODEL") or "google/siglip-so400m-patch14-384").strip()
    page_pick_n = max(1, int(float(cfg.get("WORKS_PAGE_SAMPLE_COUNT", 4)) or 4))
    user_agent = str(cfg.get("EH_USER_AGENT") or "AutoEhHunter/1.0").strip()
    cookie = str(cfg.get("EH_COOKIE") or "").strip()
    http_proxy = str(cfg.get("EH_HTTP_PROXY") or "").strip()
    https_proxy = str(cfg.get("EH_HTTPS_PROXY") or "").strip()
    lrr_base = _normalize_lrr_base(str(cfg.get("LRR_BASE") or ""))
    lrr_api_key = str(cfg.get("LRR_API_KEY") or "").strip()

    session = requests.Session()
    session.trust_env = False
    session.headers.update({"User-Agent": user_agent or "AutoEhHunter/1.0"})
    if cookie:
        session.headers.update({"Cookie": cookie})
    if http_proxy:
        session.proxies["http"] = http_proxy
    if https_proxy:
        session.proxies["https"] = https_proxy

    picked_eh = 0
    completed_eh = 0
    failed_eh = 0
    picked_works = 0
    completed_works = 0
    failed_works = 0

    try:
        with psycopg.connect(dsn) as conn:
            _acquire_table_slot("eh_works")
            try:
                pending_eh = _count_pending_eh(conn)
                candidates = _pick_candidates(conn, include_fail=include_fail, limit=limit)
                conn.commit()
                picked_eh = len(candidates)
                for i, item in enumerate(candidates, start=1):
                    if _worker_stop.is_set():
                        break
                    gid = int(item.get("gid") or 0)
                    token = str(item.get("token") or "")
                    raw = item.get("raw") or {}
                    thumb = str((raw.get("thumb") if isinstance(raw, dict) else "") or "").strip()
                    referer = str(item.get("eh_url") or item.get("ex_url") or "").strip()
                    _update_worker_status(
                        running=True,
                        table="eh_works",
                        phase="processing",
                        picked=picked_eh,
                        completed=completed_eh,
                        failed=failed_eh,
                        current=i,
                        total=pending_eh,
                    )
                    try:
                        if not thumb:
                            thumb, eh_ref, ex_ref = _refresh_thumb_from_api(conn, session, gid, token, timeout_s=timeout_s)
                            referer = str(eh_ref or ex_ref or referer).strip()
                            if not thumb:
                                raise RuntimeError("thumb missing")
                        if sleep_s > 0:
                            time.sleep(sleep_s)
                        try:
                            img = _fetch_cover_bytes(session, thumb, referer, timeout_s=timeout_s)
                        except Exception:
                            refreshed_thumb, eh_ref, ex_ref = _refresh_thumb_from_api(conn, session, gid, token, timeout_s=timeout_s)
                            if not refreshed_thumb or refreshed_thumb == thumb:
                                raise
                            thumb = refreshed_thumb
                            referer = str(eh_ref or ex_ref or referer).strip()
                            img = _fetch_cover_bytes(session, thumb, referer, timeout_s=timeout_s)
                        vec = _embed_image_siglip(img, model_id)
                        if not vec:
                            raise RuntimeError("embedding empty")
                        _mark_success(conn, gid, token, vec)
                        conn.commit()
                        completed_eh += 1
                        _update_worker_status(completed=completed_eh, failed=failed_eh)
                    except Exception as e:
                        print(f"[eh_cover_embedding] gid={gid} token={token} failed: {e}", file=sys.stderr)
                        print(traceback.format_exc(), file=sys.stderr)
                        _mark_fail(conn, gid, token)
                        conn.commit()
                        failed_eh += 1
                        _update_worker_status(completed=completed_eh, failed=failed_eh)
            finally:
                _release_table_slot("eh_works")

            if lrr_base and not _worker_stop.is_set():
                rng = random.Random()
                _acquire_table_slot("works")
                try:
                    pending_works = _count_pending_works(conn)
                    work_candidates = _pick_work_candidates(conn, include_fail=include_fail, limit=limit)
                    conn.commit()
                    picked_works = len(work_candidates)
                    for i, item in enumerate(work_candidates, start=1):
                        if _worker_stop.is_set():
                            break
                        arcid = str(item.get("arcid") or "").strip()
                        if not arcid:
                            continue
                        _update_worker_status(
                            running=True,
                            table="works",
                            phase="processing",
                            picked=picked_works,
                            completed=completed_works,
                            failed=failed_works,
                            current=i,
                            total=pending_works,
                        )
                        try:
                            cover_img = _fetch_lrr_thumb(session, lrr_base, arcid, lrr_api_key, timeout_s=timeout_s)
                            cover_vec = _embed_image_siglip(cover_img, model_id)
                            if not cover_vec:
                                raise RuntimeError("cover embedding empty")

                            pages = _lrr_get_archive_pages(session, lrr_base, arcid, lrr_api_key, timeout_s=timeout_s)
                            _cover_url, inner_urls = _pick_lrr_page_urls(pages, rng, inner_k=page_pick_n)
                            if not inner_urls:
                                raise RuntimeError("no usable inner pages")
                            inner_vecs: list[list[float]] = []
                            for u in inner_urls:
                                if _worker_stop.is_set():
                                    break
                                b = _fetch_lrr_page_bytes(session, u, lrr_api_key, timeout_s=timeout_s)
                                v = _embed_image_siglip(b, model_id)
                                if v:
                                    inner_vecs.append(v)
                            page_vec = _average_l2(inner_vecs)
                            if not page_vec:
                                raise RuntimeError("inner page embedding empty")

                            _mark_work_success(conn, arcid, cover_vec, page_vec)
                            conn.commit()
                            completed_works += 1
                            _update_worker_status(completed=completed_works, failed=failed_works)
                        except Exception as e:
                            print(f"[work_cover_embedding] arcid={arcid} failed: {e}", file=sys.stderr)
                            print(traceback.format_exc(), file=sys.stderr)
                            _mark_work_fail(conn, arcid)
                            conn.commit()
                            failed_works += 1
                            _update_worker_status(completed=completed_works, failed=failed_works)
                finally:
                    _release_table_slot("works")
    except psycopg.OperationalError:
        return {"picked": 0, "completed": 0, "failed": 0}

    return {
        "picked": picked_eh + picked_works,
        "completed": completed_eh + completed_works,
        "failed": failed_eh + failed_works,
        "picked_eh": picked_eh,
        "completed_eh": completed_eh,
        "failed_eh": failed_eh,
        "picked_works": picked_works,
        "completed_works": completed_works,
        "failed_works": failed_works,
    }


def _worker_loop() -> None:
    _update_worker_status(running=True, phase="idle", table="", picked=0, completed=0, failed=0, current=0, total=0)
    while not _worker_stop.is_set():
        try:
            stats = run_eh_cover_embedding_once(include_fail=False, limit=10)
            if int(stats.get("picked") or 0) > 0:
                continue
        except psycopg.OperationalError:
            pass
        except Exception as e:
            print(f"[eh_cover_embedding] worker loop error: {e}", file=sys.stderr)
            print(traceback.format_exc(), file=sys.stderr)
        _worker_stop.wait(8.0)
    _update_worker_status(running=False, phase="stopped" if _read_worker_status().get("stopped_by_user") else "idle", table="", current=0, total=0)


def start_eh_cover_embedding_worker() -> None:
    global _worker_thread
    with _worker_lock:
        if bool(_read_worker_status().get("stopped_by_user")):
            return
        if _worker_thread and _worker_thread.is_alive():
            return
        _worker_stop.clear()
        _update_worker_status(running=True, phase="idle", table="", current=0, total=0)
        _worker_thread = threading.Thread(target=_worker_loop, name="eh-cover-embed-worker", daemon=True)
        _worker_thread.start()


def stop_eh_cover_embedding_worker() -> None:
    _worker_stop.set()
    _update_worker_status(running=False, phase="idle", table="", current=0, total=0)


def stop_eh_cover_embedding_worker_until_restart() -> None:
    _update_worker_status(stopped_by_user=True)
    _worker_stop.set()


def get_eh_cover_embedding_worker_status() -> dict[str, Any]:
    st = _read_worker_status()
    thread_alive = bool(_worker_thread and _worker_thread.is_alive())
    st["thread_alive"] = thread_alive
    if bool(st.get("stopped_by_user")):
        st["phase"] = "stopped"
        st["running"] = False
    elif thread_alive and st.get("phase") in {"idle", "processing"}:
        st["running"] = True
    return st


def reset_failed_eh_cover_embeddings() -> int:
    dsn = str(db_dsn() or "").strip()
    if not dsn:
        return 0
    sql = (
        "UPDATE eh_works "
        "SET cover_embedding_status = 'pending', updated_at = now() "
        "WHERE cover_embedding IS NULL AND cover_embedding_status = 'fail'"
    )
    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute(sql)
            n = int(cur.rowcount or 0)
        conn.commit()
    return n
