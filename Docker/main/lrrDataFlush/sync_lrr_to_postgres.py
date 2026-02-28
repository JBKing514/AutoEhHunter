#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import datetime as _dt
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any


def _split_tags(tags: Any) -> list[str]:
    if isinstance(tags, list):
        return [str(x).strip() for x in tags if str(x).strip()]
    s = str(tags or "")
    return [t.strip() for t in s.split(",") if t.strip()]


def _extract_epoch_tag(tags_list: list[str], keys: list[str]) -> int:
    for t in tags_list:
        for k in keys:
            if not t.startswith(k):
                continue
            val = t[len(k) :].strip()
            try:
                return int(val)
            except Exception:
                continue
    return 0


def _http_get_json(url: str, apikey: str | None, timeout: float) -> Any:
    req = urllib.request.Request(url, method="GET")
    req.add_header("Accept", "application/json")
    req.add_header("User-Agent", "lrr-sync/1.0")
    if apikey:
        token = base64.b64encode(apikey.encode("utf-8")).decode("ascii")
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
    except urllib.error.HTTPError as e:
        body = ""
        try:
            body = e.read().decode("utf-8", errors="replace")
        except Exception:
            pass
        raise RuntimeError(f"HTTP {e.code} for {url}\n{body}")
    except urllib.error.URLError as e:
        raise RuntimeError(f"Network error for {url}: {e}")
    return json.loads(raw.decode("utf-8"))


def _page_search(base_url: str, *, start: int, sortby: str, order: str, filter_expr: str, apikey: str | None, timeout: float) -> list[dict[str, Any]]:
    params = {
        "filter": str(filter_expr or ""),
        "start": str(int(start)),
        "sortby": sortby,
        "order": order,
    }
    url = base_url.rstrip("/") + "/api/search?" + urllib.parse.urlencode(params)
    payload = _http_get_json(url, apikey=apikey, timeout=timeout)
    if not isinstance(payload, dict):
        raise RuntimeError(f"Unexpected response from {url}")
    data = payload.get("data")
    if not isinstance(data, list):
        raise RuntimeError(f"Unexpected data format from {url}")
    return [x for x in data if isinstance(x, dict)]


def _upsert_works(cur: Any, rows: list[tuple[Any, ...]]) -> None:
    if not rows:
        return
    sql = (
        "INSERT INTO works (arcid, title, tags, eh_posted, date_added, raw, last_seen_at) "
        "VALUES (%s, %s, %s, %s, %s, %s::jsonb, now()) "
        "ON CONFLICT (arcid) DO UPDATE SET "
        "title = EXCLUDED.title, "
        "tags = CASE WHEN cardinality(EXCLUDED.tags) > 0 THEN EXCLUDED.tags ELSE works.tags END, "
        "eh_posted = COALESCE(EXCLUDED.eh_posted, works.eh_posted), "
        "date_added = COALESCE(EXCLUDED.date_added, works.date_added), "
        "raw = EXCLUDED.raw, "
        "last_seen_at = now()"
    )
    cur.executemany(sql, rows)


def _insert_events(cur: Any, rows: list[tuple[Any, ...]]) -> None:
    if not rows:
        return
    sql = (
        "INSERT INTO read_events (arcid, read_time, source_file, raw) "
        "VALUES (%s, %s, %s, %s::jsonb) "
        "ON CONFLICT (arcid, read_time) DO NOTHING"
    )
    cur.executemany(sql, rows)


def sync_lrr_to_pg(
    *,
    dsn: str,
    base_url: str,
    apikey: str | None,
    timeout: float,
    sleep_s: float,
    filter_expr: str,
    reads_hours: float,
    full_reads: bool,
    include_tanks: bool,
    include_lastread_as_event: bool,
    prune_not_seen: bool,
    batch_size: int,
) -> dict[str, int]:
    try:
        import psycopg
    except Exception as e:
        raise RuntimeError(f"Missing dependency psycopg[binary]: {e}")

    now_ep = int(time.time())
    cutoff = int(now_ep - max(1.0, float(reads_hours)) * 3600)
    started_at = _dt.datetime.now(tz=_dt.timezone.utc)

    total_scanned = 0
    total_works = 0
    total_events = 0
    pass1_seen_works = 0

    conn = psycopg.connect(dsn)
    conn.execute("SET statement_timeout = '5min'")
    try:
        works_rows: list[tuple[Any, ...]] = []
        event_rows: list[tuple[Any, ...]] = []

        # Pass 1: full metadata -> works upsert
        start = 0
        while True:
            page = _page_search(
                base_url,
                start=start,
                sortby="title",
                order="asc",
                filter_expr=filter_expr,
                apikey=apikey,
                timeout=timeout,
            )
            if not page:
                break
            for arc in page:
                total_scanned += 1
                arcid = str(arc.get("arcid") or "").strip()
                if not arcid:
                    continue
                pass1_seen_works += 1
                tags_list = _split_tags(arc.get("tags") or "")
                eh_posted = _extract_epoch_tag(tags_list, ["timestamp:", "时间戳:"]) or None
                date_added = _extract_epoch_tag(tags_list, ["date_added:"]) or None
                lastreadtime = int(arc.get("lastreadtime") or 0) or None
                raw_json = json.dumps(
                    {
                        "arcid": arcid,
                        "title": arc.get("title") or "",
                        "tags": tags_list,
                        "lastreadtime": lastreadtime,
                        "eh_posted": eh_posted,
                        "date_added": date_added,
                    },
                    ensure_ascii=False,
                )
                works_rows.append((arcid, str(arc.get("title") or ""), tags_list, eh_posted, date_added, raw_json))
                if include_lastread_as_event and int(lastreadtime or 0) > 0:
                    event_rows.append((arcid, int(lastreadtime), "lrr_sync:metadata", raw_json))

                if len(works_rows) >= batch_size or len(event_rows) >= batch_size:
                    with conn.cursor() as cur:
                        _upsert_works(cur, works_rows)
                        _insert_events(cur, event_rows)
                    conn.commit()
                    total_works += len(works_rows)
                    total_events += len(event_rows)
                    works_rows.clear()
                    event_rows.clear()

            start += len(page)
            if sleep_s > 0:
                time.sleep(sleep_s)

        if works_rows or event_rows:
            with conn.cursor() as cur:
                _upsert_works(cur, works_rows)
                _insert_events(cur, event_rows)
            conn.commit()
            total_works += len(works_rows)
            total_events += len(event_rows)
            works_rows.clear()
            event_rows.clear()

        # Pass 2: recent reads -> read_events only
        start = 0
        while True:
            page = _page_search(
                base_url,
                start=start,
                sortby="lastread",
                order="asc",
                filter_expr=filter_expr,
                apikey=apikey,
                timeout=timeout,
            )
            if not page:
                break
            stop = False
            for arc in page:
                total_scanned += 1
                arcid = str(arc.get("arcid") or "").strip()
                if not arcid:
                    continue
                if (not include_tanks) and arcid.upper().startswith("TANK"):
                    continue
                read_time = int(arc.get("lastreadtime") or 0)
                if read_time <= 0:
                    continue
                if (not full_reads) and read_time < cutoff:
                    stop = True
                    continue

                tags_list = _split_tags(arc.get("tags") or "")
                raw_json = json.dumps(
                    {
                        "arcid": arcid,
                        "title": arc.get("title") or "",
                        "tags": tags_list,
                        "read_time": read_time,
                    },
                    ensure_ascii=False,
                )
                event_rows.append((arcid, read_time, "lrr_sync:recent_reads", raw_json))

                if len(event_rows) >= batch_size:
                    with conn.cursor() as cur:
                        _insert_events(cur, event_rows)
                    conn.commit()
                    total_events += len(event_rows)
                    event_rows.clear()

            if stop:
                break
            start += len(page)
            if sleep_s > 0:
                time.sleep(sleep_s)

        if event_rows:
            with conn.cursor() as cur:
                _insert_events(cur, event_rows)
            conn.commit()
            total_events += len(event_rows)

        pruned = 0
        if prune_not_seen:
            if pass1_seen_works <= 0:
                raise RuntimeError("Refusing prune-not-seen: metadata pass returned 0 works")
            with conn.cursor() as cur:
                cur.execute("SELECT count(*) FROM works WHERE last_seen_at < %s", (started_at,))
                (pruned,) = cur.fetchone() or (0,)
                cur.execute("DELETE FROM works WHERE last_seen_at < %s", (started_at,))
            conn.commit()

        return {
            "scanned": int(total_scanned),
            "works_upserted": int(total_works),
            "events_inserted": int(total_events),
            "pruned": int(pruned),
        }
    finally:
        conn.close()


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="Sync LANraragi API data directly into Postgres")
    ap.add_argument("--dsn", required=True)
    ap.add_argument("--base-url", required=True)
    ap.add_argument("--apikey", default="")
    ap.add_argument("--timeout", type=float, default=30.0)
    ap.add_argument("--sleep", type=float, default=0.0)
    ap.add_argument("--filter", default="")
    ap.add_argument("--reads-hours", type=float, default=24.0)
    ap.add_argument("--full-reads", action="store_true")
    ap.add_argument("--include-tanks", action="store_true")
    ap.add_argument("--include-lastread-as-event", action="store_true")
    ap.add_argument("--prune-not-seen", action="store_true")
    ap.add_argument("--batch-size", type=int, default=1000)
    args = ap.parse_args(argv)

    try:
        stat = sync_lrr_to_pg(
            dsn=str(args.dsn),
            base_url=str(args.base_url),
            apikey=(str(args.apikey).strip() or None),
            timeout=float(args.timeout),
            sleep_s=float(args.sleep),
            filter_expr=str(args.filter or ""),
            reads_hours=float(args.reads_hours),
            full_reads=bool(args.full_reads),
            include_tanks=bool(args.include_tanks),
            include_lastread_as_event=bool(args.include_lastread_as_event),
            prune_not_seen=bool(args.prune_not_seen),
            batch_size=max(100, int(args.batch_size)),
        )
        print(
            "LRR sync done. "
            f"scanned={stat['scanned']} "
            f"works_upserted={stat['works_upserted']} "
            f"events_inserted={stat['events_inserted']} "
            f"pruned={stat['pruned']}",
            file=sys.stderr,
        )
        return 0
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
