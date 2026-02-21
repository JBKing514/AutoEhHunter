#!/usr/bin/env python3
"""Ingest LANraragi JSONL exports into PostgreSQL.

This script is designed to be run outside the LANraragi container.

Input formats supported (as produced by the earlier export scripts):
  - export_lrr_metadata.py (full library export)
  - export_lrr_recent_reads.py (recent reads; emits read_time)

Schema:
  See schema.sql (works + read_events).

Dependencies:
  pip install "psycopg[binary]"
"""

from __future__ import annotations

import argparse
import json
import os
import datetime as _dt
from pathlib import Path
import sys
from typing import Any, Iterable


def _iter_input_files(inputs: list[str]) -> list[Path]:
    files: list[Path] = []
    for raw in inputs:
        p = Path(raw)
        if p.is_dir():
            files.extend(sorted(p.glob("*.jsonl")))
        else:
            files.append(p)
    # De-dup while preserving order
    seen: set[str] = set()
    out: list[Path] = []
    for f in files:
        key = str(f.resolve())
        if key in seen:
            continue
        seen.add(key)
        out.append(f)
    return out


def _as_str_list(v: Any) -> list[str]:
    if v is None:
        return []
    if isinstance(v, list):
        return [str(x) for x in v if str(x).strip()]
    if isinstance(v, str):
        # Accept comma-separated raw tags
        return [t.strip() for t in v.split(",") if t.strip()]
    return [str(v)]


def _as_int(v: Any) -> int:
    if v is None:
        return 0
    try:
        return int(v)
    except Exception:
        return 0


def _read_jsonl(path: Path) -> Iterable[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, start=1):
            s = line.strip()
            if not s:
                continue
            try:
                obj = json.loads(s)
            except Exception as e:
                raise RuntimeError(f"Invalid JSON at {path}:{line_no}: {e}")
            if not isinstance(obj, dict):
                continue
            yield obj


def _load_schema_text(schema_path: Path) -> str:
    return schema_path.read_text(encoding="utf-8")


def _chunked(seq: list[Any], n: int) -> Iterable[list[Any]]:
    for i in range(0, len(seq), n):
        yield seq[i : i + n]


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(
        description="Ingest LANraragi JSONL exports into PostgreSQL (works + read_events)."
    )
    ap.add_argument(
        "--dsn",
        required=True,
        help=(
            "PostgreSQL DSN, e.g. postgresql://user:pass@host:5432/dbname "
            "(or use libpq keywords like 'host=... dbname=...')"
        ),
    )
    ap.add_argument(
        "--input",
        required=True,
        nargs="+",
        help="Input .jsonl file(s) or directories (directories will ingest *.jsonl)",
    )
    ap.add_argument(
        "--schema",
        default="schema.sql",
        help="Path to schema.sql (used with --init-schema)",
    )
    ap.add_argument(
        "--init-schema",
        action="store_true",
        help="Create tables/indexes if they don't exist",
    )
    ap.add_argument(
        "--batch-size",
        type=int,
        default=1000,
        help="Rows per DB batch (default: 1000)",
    )
    ap.add_argument(
        "--source-mode",
        choices=["path", "basename"],
        default="basename",
        help="Store source_file as full path or just basename (default: basename)",
    )
    ap.add_argument(
        "--include-lastread-as-event",
        action="store_true",
        help=(
            "Also insert a read_event from lastreadtime when read_time is not present. "
            "(Useful when ingesting full library exports.)"
        ),
    )
    ap.add_argument(
        "--dry-run",
        action="store_true",
        help="Parse inputs but do not write to the database",
    )

    ap.add_argument(
        "--prune-not-seen",
        action="store_true",
        help=(
            "After ingest, delete works not seen in this ingest run. "
            "Use this ONLY when your inputs include a full library snapshot export, "
            "otherwise you'll delete most of your library."
        ),
    )

    args = ap.parse_args(argv)

    files = _iter_input_files(args.input)
    if not files:
        print("No input files found.", file=sys.stderr)
        return 2

    try:
        import psycopg
    except Exception as e:
        print(
            "Missing dependency psycopg. Install with: pip install \"psycopg[binary]\"\n"
            + str(e),
            file=sys.stderr,
        )
        return 2

    run_started_at = _dt.datetime.now(tz=_dt.timezone.utc)

    if args.dry_run:
        conn = None
    else:
        conn = psycopg.connect(args.dsn)
        conn.execute("SET statement_timeout = '5min'")

    try:
        if conn and args.init_schema:
            schema_path = Path(args.schema)
            schema_sql = _load_schema_text(schema_path)
            with conn.cursor() as cur:
                cur.execute(schema_sql)
            conn.commit()

        works_upsert_sql = (
            "INSERT INTO works (arcid, title, tags, eh_posted, date_added, lastreadtime, raw, last_seen_at) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb, now()) "
            "ON CONFLICT (arcid) DO UPDATE SET "
            "title = EXCLUDED.title, "
            "tags = CASE WHEN cardinality(EXCLUDED.tags) > 0 THEN EXCLUDED.tags ELSE works.tags END, "
            "eh_posted = COALESCE(EXCLUDED.eh_posted, works.eh_posted), "
            "date_added = COALESCE(EXCLUDED.date_added, works.date_added), "
            "lastreadtime = GREATEST(COALESCE(works.lastreadtime,0), COALESCE(EXCLUDED.lastreadtime,0)), "
            "raw = EXCLUDED.raw, "
            "last_seen_at = now()"
        )

        read_event_insert_sql = (
            "INSERT INTO read_events (arcid, read_time, source_file, raw) "
            "VALUES (%s, %s, %s, %s::jsonb) "
            "ON CONFLICT (arcid, read_time) DO NOTHING"
        )

        total_lines = 0
        total_works = 0
        total_events = 0

        for path in files:
            if not path.exists():
                print(f"Skipping missing file: {path}", file=sys.stderr)
                continue

            source_file = str(path) if args.source_mode == "path" else path.name

            works_rows: list[tuple[Any, ...]] = []
            event_rows: list[tuple[Any, ...]] = []

            for obj in _read_jsonl(path):
                total_lines += 1

                arcid = obj.get("arcid")
                if not arcid:
                    continue
                arcid = str(arcid)

                title = str(obj.get("title") or "")
                tags = _as_str_list(obj.get("tags"))

                eh_posted = _as_int(obj.get("eh_posted")) or None
                date_added = _as_int(obj.get("date_added")) or None
                lastreadtime = _as_int(obj.get("lastreadtime")) or None

                raw_json = json.dumps(obj, ensure_ascii=False)

                works_rows.append(
                    (arcid, title, tags, eh_posted, date_added, lastreadtime, raw_json)
                )

                read_time = 0
                if "read_time" in obj:
                    read_time = _as_int(obj.get("read_time"))
                elif args.include_lastread_as_event:
                    read_time = _as_int(obj.get("lastreadtime"))

                if read_time > 0:
                    event_rows.append((arcid, read_time, source_file, raw_json))

                if (
                    len(works_rows) >= args.batch_size
                    or len(event_rows) >= args.batch_size
                ):
                    if conn:
                        with conn.cursor() as cur:
                            cur.executemany(works_upsert_sql, works_rows)
                            if event_rows:
                                cur.executemany(read_event_insert_sql, event_rows)
                        conn.commit()
                    total_works += len(works_rows)
                    total_events += len(event_rows)
                    works_rows.clear()
                    event_rows.clear()

            # Flush remaining rows for this file
            if works_rows or event_rows:
                if conn:
                    with conn.cursor() as cur:
                        if works_rows:
                            cur.executemany(works_upsert_sql, works_rows)
                        if event_rows:
                            cur.executemany(read_event_insert_sql, event_rows)
                    conn.commit()
                total_works += len(works_rows)
                total_events += len(event_rows)

            print(
                f"Ingested {path} (lines={total_lines}, works={total_works}, events={total_events})",
                file=sys.stderr,
            )

        if conn and args.prune_not_seen:
            # Any work not upserted during this run will have an older last_seen_at.
            # This is only safe if a full library snapshot was ingested.
            with conn.cursor() as cur:
                cur.execute("SELECT count(*) FROM works WHERE last_seen_at < %s", (run_started_at,))
                (stale_count,) = cur.fetchone() or (0,)
                cur.execute("DELETE FROM works WHERE last_seen_at < %s", (run_started_at,))
            conn.commit()
            print(f"Pruned {stale_count} works not seen in this run.", file=sys.stderr)

        print(
            f"Done. Parsed lines={total_lines}, upserted_works={total_works}, inserted_events={total_events}",
            file=sys.stderr,
        )
        if args.dry_run:
            print("Dry run: no database writes performed.", file=sys.stderr)

    except Exception as e:
        if conn:
            conn.rollback()
        print(f"ERROR: {e}", file=sys.stderr)
        return 1
    finally:
        if conn:
            conn.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
