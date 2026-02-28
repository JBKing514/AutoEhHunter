import logging
import re
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence, Tuple
import threading

import psycopg
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from hunterAgent.core.config import Settings


logger = logging.getLogger(__name__)

_pool_lock = threading.Lock()
_pools: dict[str, ConnectionPool] = {}


class _PooledConnection:
    def __init__(self, pool: ConnectionPool, conn: psycopg.Connection):
        self._pool = pool
        self._conn = conn
        self._returned = False

    def __getattr__(self, item: str):
        return getattr(self._conn, item)

    def close(self) -> None:
        if self._returned:
            return
        self._returned = True
        self._pool.putconn(self._conn)


def _get_pool(settings: Settings) -> ConnectionPool:
    dsn = str(settings.postgres_dsn or "").strip()
    if not dsn:
        raise RuntimeError("Missing POSTGRES_DSN")
    with _pool_lock:
        existing = _pools.get(dsn)
        if existing is not None:
            return existing
        pool = ConnectionPool(
            conninfo=dsn,
            min_size=1,
            max_size=8,
            timeout=30,
            open=True,
        )
        _pools[dsn] = pool
        return pool


def get_db_connection(settings: Settings):
    pool = _get_pool(settings)
    return _PooledConnection(pool, pool.getconn())


@dataclass
class HotTagCache:
    tags: List[str]
    fetched_at: float


_hot_tag_cache: Optional[HotTagCache] = None


def get_hot_tags(settings: Settings) -> List[str]:
    """Return frequent tags from works.tags.

    Cached in-process to avoid a full-table unnest per request.
    """

    global _hot_tag_cache
    now = time.time()
    if _hot_tag_cache is not None:
        if now - _hot_tag_cache.fetched_at <= float(settings.hot_tag_cache_ttl_s):
            return list(_hot_tag_cache.tags)

    sql = (
        "SELECT tag, count(*) as freq "
        "FROM (SELECT unnest(tags) as tag FROM works) as t "
        "GROUP BY tag "
        "HAVING count(*) > %s "
        "ORDER BY freq DESC"
    )

    conn = get_db_connection(settings)
    try:
        with conn.cursor() as cur:
            cur.execute(sql, (int(settings.hot_tag_min_freq),))
            rows = cur.fetchall() or []
    finally:
        conn.close()

    tags = [str(r[0]) for r in rows if r and r[0] is not None]
    _hot_tag_cache = HotTagCache(tags=tags, fetched_at=now)
    logger.info("hot_tags fetched=%d min_freq>%d", len(tags), settings.hot_tag_min_freq)
    return list(tags)


def get_read_events_by_period(
    settings: Settings, start_epoch: int, end_epoch: int, limit: int = 5000
) -> List[Dict[str, Any]]:
    sql = (
        "SELECT e.arcid, e.read_time, e.source_file, "
        "w.title, w.tags, w.eh_posted, w.date_added, w.lastreadtime "
        "FROM read_events e "
        "JOIN works w ON w.arcid = e.arcid "
        "WHERE e.read_time >= %s AND e.read_time < %s "
        "ORDER BY e.read_time DESC "
        "LIMIT %s"
    )
    conn = get_db_connection(settings)
    try:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(sql, (int(start_epoch), int(end_epoch), int(limit)))
            rows = cur.fetchall() or []
            return [dict(r) for r in rows]
    finally:
        conn.close()


def fetch_works_by_arcids(settings: Settings, arcids: Sequence[str]) -> List[Dict[str, Any]]:
    if not arcids:
        return []
    sql = (
        "SELECT arcid, title, tags, description, eh_posted, date_added, lastreadtime, last_seen_at "
        "FROM works WHERE arcid = ANY(%s)"
    )
    conn = get_db_connection(settings)
    try:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(sql, (list(arcids),))
            rows = cur.fetchall() or []
            # Keep ordering stable: return in the same order as arcids.
            by_id = {str(r["arcid"]): dict(r) for r in rows}
            out = []
            for a in arcids:
                if str(a) in by_id:
                    out.append(by_id[str(a)])
            return out
    finally:
        conn.close()


def get_works_by_date_added(
    settings: Settings, start_epoch: int, end_epoch: int, limit: int = 5000
) -> List[Dict[str, Any]]:
    # date_added may be stored as seconds or milliseconds depending on ingest path.
    # Normalize to seconds in SQL so profile windows are stable across datasets.
    sql = (
        "SELECT arcid, title, tags, description, eh_posted, date_added, lastreadtime "
        "FROM works "
        "WHERE date_added IS NOT NULL "
        "AND (CASE WHEN date_added >= 100000000000 THEN date_added / 1000 ELSE date_added END) >= %s "
        "AND (CASE WHEN date_added >= 100000000000 THEN date_added / 1000 ELSE date_added END) < %s "
        "ORDER BY (CASE WHEN date_added >= 100000000000 THEN date_added / 1000 ELSE date_added END) DESC "
        "LIMIT %s"
    )
    conn = get_db_connection(settings)
    try:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(sql, (int(start_epoch), int(end_epoch), int(limit)))
            rows = cur.fetchall() or []
            return [dict(r) for r in rows]
    finally:
        conn.close()


def _vector_literal(vec: List[float]) -> str:
    return "[" + ",".join(repr(float(x)) for x in vec) + "]"


def _parse_vector_text(text: str) -> List[float]:
    s = str(text or "").strip()
    if not s:
        return []
    if s.startswith("[") and s.endswith("]"):
        s = s[1:-1]
    if not s.strip():
        return []
    parts = re.split(r"\s*,\s*", s.strip())
    out: List[float] = []
    for p in parts:
        if not p:
            continue
        out.append(float(p))
    return out


def get_visual_embedding_by_arcid(settings: Settings, arcid: str) -> Optional[Dict[str, Any]]:
    sql = (
        "SELECT arcid, title, visual_embedding::text as visual_vec "
        "FROM works WHERE arcid = %s AND visual_embedding IS NOT NULL LIMIT 1"
    )
    conn = get_db_connection(settings)
    try:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(sql, (str(arcid),))
            row = cur.fetchone()
            if not row:
                return None
            vec = _parse_vector_text(str(row.get("visual_vec") or ""))
            if not vec:
                return None
            return {"arcid": str(row.get("arcid")), "title": row.get("title"), "visual_embedding": vec}
    finally:
        conn.close()


def get_visual_embedding_by_title(settings: Settings, title: str) -> Optional[Dict[str, Any]]:
    t = str(title or "").strip()
    if not t:
        return None
    sql = (
        "SELECT arcid, title, visual_embedding::text as visual_vec "
        "FROM works "
        "WHERE visual_embedding IS NOT NULL "
        "AND (title = %s OR title ILIKE %s) "
        "ORDER BY CASE WHEN title = %s THEN 0 ELSE 1 END, lastreadtime DESC NULLS LAST "
        "LIMIT 1"
    )
    conn = get_db_connection(settings)
    try:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(sql, (t, f"%{t}%", t))
            row = cur.fetchone()
            if not row:
                return None
            vec = _parse_vector_text(str(row.get("visual_vec") or ""))
            if not vec:
                return None
            return {"arcid": str(row.get("arcid")), "title": row.get("title"), "visual_embedding": vec}
    finally:
        conn.close()


def search_by_text(
    settings: Settings,
    query: str,
    *,
    tags: Optional[Sequence[str]] = None,
    limit: int = 50,
) -> List[str]:
    q = (query or "").strip()
    if not q:
        return []
    like = f"%{q}%"
    where = "(title ILIKE %s OR description ILIKE %s OR array_to_string(tags, ' ') ILIKE %s)"
    params: List[Any] = [like, like, like]
    if tags:
        where += " AND tags && %s"
        params.append(list(tags))
    sql = f"SELECT arcid FROM works WHERE {where} ORDER BY lastreadtime DESC NULLS LAST, arcid LIMIT %s"
    params.append(int(limit))

    conn = get_db_connection(settings)
    try:
        with conn.cursor() as cur:
            cur.execute(sql, tuple(params))
            rows = cur.fetchall() or []
            return [str(r[0]) for r in rows]
    finally:
        conn.close()


def search_by_desc_vector(
    settings: Settings,
    query_vec: List[float],
    *,
    tags: Optional[Sequence[str]] = None,
    limit: int = 50,
) -> List[str]:
    if not query_vec:
        return []
    v = _vector_literal(query_vec)
    where = "desc_embedding IS NOT NULL"
    params: List[Any] = []
    if tags:
        where += " AND tags && %s"
        params.append(list(tags))
    # Use cosine distance (<=>) to be robust even if desc embeddings are not normalized.
    sql = f"SELECT arcid FROM works WHERE {where} ORDER BY desc_embedding <=> (%s)::vector LIMIT %s"
    params.extend([v, int(limit)])

    conn = get_db_connection(settings)
    try:
        with conn.cursor() as cur:
            cur.execute(sql, tuple(params))
            rows = cur.fetchall() or []
            return [str(r[0]) for r in rows]
    finally:
        conn.close()


def search_by_visual_vector(
    settings: Settings,
    query_vec: List[float],
    *,
    tags: Optional[Sequence[str]] = None,
    limit: int = 50,
) -> List[str]:
    if not query_vec:
        return []
    v = _vector_literal(query_vec)
    where = "visual_embedding IS NOT NULL"
    params: List[Any] = []
    if tags:
        where += " AND tags && %s"
        params.append(list(tags))
    # visual_embedding is L2-normalized in your ingest script, but cosine is still safe.
    sql = f"SELECT arcid FROM works WHERE {where} ORDER BY visual_embedding <=> (%s)::vector LIMIT %s"
    params.extend([v, int(limit)])

    conn = get_db_connection(settings)
    try:
        with conn.cursor() as cur:
            cur.execute(sql, tuple(params))
            rows = cur.fetchall() or []
            return [str(r[0]) for r in rows]
    finally:
        conn.close()


def get_profile_samples_from_reads(
    settings: Settings,
    start_epoch: int,
    end_epoch: int,
    limit: int = 800,
) -> List[Dict[str, Any]]:
    sql = (
        "SELECT e.arcid, e.read_time, w.title, w.tags, "
        "w.visual_embedding::text as visual_vec, w.page_visual_embedding::text as page_visual_vec "
        "FROM read_events e "
        "JOIN works w ON w.arcid = e.arcid "
        "WHERE e.read_time >= %s AND e.read_time < %s "
        "ORDER BY e.read_time DESC "
        "LIMIT %s"
    )
    conn = get_db_connection(settings)
    try:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(sql, (int(start_epoch), int(end_epoch), int(limit)))
            rows = cur.fetchall() or []
            out: List[Dict[str, Any]] = []
            for r in rows:
                d = dict(r)
                d["visual_embedding"] = _parse_vector_text(str(d.pop("visual_vec", "") or ""))
                d["page_visual_embedding"] = _parse_vector_text(str(d.pop("page_visual_vec", "") or ""))
                out.append(d)
            return out
    finally:
        conn.close()


def get_profile_samples_from_inventory(
    settings: Settings,
    start_epoch: int,
    end_epoch: int,
    limit: int = 800,
) -> List[Dict[str, Any]]:
    sql = (
        "SELECT arcid, title, tags, visual_embedding::text as visual_vec, page_visual_embedding::text as page_visual_vec "
        "FROM works "
        "WHERE date_added IS NOT NULL "
        "AND (CASE WHEN date_added >= 100000000000 THEN date_added / 1000 ELSE date_added END) >= %s "
        "AND (CASE WHEN date_added >= 100000000000 THEN date_added / 1000 ELSE date_added END) < %s "
        "ORDER BY (CASE WHEN date_added >= 100000000000 THEN date_added / 1000 ELSE date_added END) DESC "
        "LIMIT %s"
    )
    conn = get_db_connection(settings)
    try:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(sql, (int(start_epoch), int(end_epoch), int(limit)))
            rows = cur.fetchall() or []
            out: List[Dict[str, Any]] = []
            for r in rows:
                d = dict(r)
                d["visual_embedding"] = _parse_vector_text(str(d.pop("visual_vec", "") or ""))
                d["page_visual_embedding"] = _parse_vector_text(str(d.pop("page_visual_vec", "") or ""))
                out.append(d)
            return out
    finally:
        conn.close()


def get_eh_candidates_by_period(
    settings: Settings,
    start_epoch: int,
    end_epoch: int,
    limit: int = 400,
) -> List[Dict[str, Any]]:
    sql = (
        "SELECT gid, token, eh_url, ex_url, title, title_jpn, tags, tags_translated, posted, "
        "cover_embedding::text as cover_vec "
        "FROM eh_works "
        "WHERE posted IS NOT NULL "
        "AND posted >= %s AND posted < %s "
        "ORDER BY posted DESC "
        "LIMIT %s"
    )
    conn = get_db_connection(settings)
    try:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(sql, (int(start_epoch), int(end_epoch), int(limit)))
            rows = cur.fetchall() or []
            out: List[Dict[str, Any]] = []
            for r in rows:
                d = dict(r)
                d["cover_embedding"] = _parse_vector_text(str(d.pop("cover_vec", "") or ""))
                out.append(d)
            return out
    finally:
        conn.close()


def search_eh_by_text(
    settings: Settings,
    query: str,
    *,
    tags: Optional[Sequence[str]] = None,
    limit: int = 50,
) -> List[str]:
    q = (query or "").strip()
    if not q:
        return []
    like = f"%{q}%"
    where = (
        "(title ILIKE %s OR title_jpn ILIKE %s OR "
        "array_to_string(tags, ' ') ILIKE %s OR array_to_string(tags_translated, ' ') ILIKE %s)"
    )
    params: List[Any] = [like, like, like, like]
    if tags:
        where += " AND tags && %s"
        params.append(list(tags))

    sql = f"SELECT gid::text, token FROM eh_works WHERE {where} ORDER BY posted DESC NULLS LAST, gid DESC LIMIT %s"
    params.append(int(limit))

    conn = get_db_connection(settings)
    try:
        with conn.cursor() as cur:
            cur.execute(sql, tuple(params))
            rows = cur.fetchall() or []
            out: List[str] = []
            for r in rows:
                gid = str(r[0])
                token = str(r[1])
                out.append(f"eh:{gid}:{token}")
            return out
    finally:
        conn.close()


def search_eh_by_cover_vector(
    settings: Settings,
    query_vec: List[float],
    *,
    tags: Optional[Sequence[str]] = None,
    limit: int = 50,
) -> List[str]:
    if not query_vec:
        return []
    v = _vector_literal(query_vec)
    where = "cover_embedding IS NOT NULL"
    params: List[Any] = []
    if tags:
        where += " AND tags && %s"
        params.append(list(tags))
    sql = f"SELECT gid::text, token FROM eh_works WHERE {where} ORDER BY cover_embedding <=> (%s)::vector LIMIT %s"
    params.extend([v, int(limit)])

    conn = get_db_connection(settings)
    try:
        with conn.cursor() as cur:
            cur.execute(sql, tuple(params))
            rows = cur.fetchall() or []
            out: List[str] = []
            for r in rows:
                gid = str(r[0])
                token = str(r[1])
                out.append(f"eh:{gid}:{token}")
            return out
    finally:
        conn.close()


def fetch_eh_works_by_ids(settings: Settings, ids: Sequence[str]) -> List[Dict[str, Any]]:
    keys: List[Tuple[str, str]] = []
    for x in ids:
        s = str(x or "")
        if not s.startswith("eh:"):
            continue
        parts = s.split(":", 2)
        if len(parts) != 3:
            continue
        keys.append((parts[1], parts[2]))
    if not keys:
        return []

    sql = (
        "SELECT gid::text as gid, token, eh_url, ex_url, title, title_jpn, tags, tags_translated, posted "
        "FROM eh_works WHERE (gid::text, token) IN (SELECT * FROM UNNEST(%s::text[], %s::text[]))"
    )
    gid_list = [k[0] for k in keys]
    token_list = [k[1] for k in keys]

    conn = get_db_connection(settings)
    try:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(sql, (gid_list, token_list))
            rows = cur.fetchall() or []
            by_id = {f"eh:{str(r['gid'])}:{str(r['token'])}": dict(r) for r in rows}
            out: List[Dict[str, Any]] = []
            for key in ids:
                row = by_id.get(str(key))
                if row is not None:
                    out.append(row)
            return out
    finally:
        conn.close()
