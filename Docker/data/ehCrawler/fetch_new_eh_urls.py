#!/usr/bin/env python3
"""Incrementally fetch newly uploaded EH gallery URLs into a queue file.

Workflow:
- Crawl EH listing pages from newest to older
- Stop when reaching the last-seen gallery checkpoint from state file
- Append only new URLs into queue file (deduplicated)
- Update checkpoint to the newest gallery seen in this run

This script is designed to work with:
  ingest_eh_metadata_to_pg.py --queue-file <same_queue_file>
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import math
import re
import sys
import time
from pathlib import Path

import requests


GALLERY_RE = re.compile(r"/g/(\d+)/([0-9A-Za-z]+)/")
ABS_GALLERY_RE = re.compile(r"https?://((?:e-hentai|exhentai)\.org)/g/(\d+)/([0-9A-Za-z]+)/")


def _extract_host(base_url: str) -> str:
    m = re.search(r"https?://((?:e-hentai|exhentai)\.org)", str(base_url or "").strip(), re.IGNORECASE)
    if m:
        return m.group(1).lower()
    return "e-hentai.org"


def _parse_gallery_url(url: str, default_base_url: str = "https://e-hentai.org") -> tuple[int, str, str]:
    s = (url or "").strip()
    m = ABS_GALLERY_RE.search(s)
    if m:
        host = m.group(1).lower()
        gid = int(m.group(2))
        token = m.group(3)
        return gid, token, f"https://{host}/g/{gid}/{token}/"

    m2 = GALLERY_RE.search(s)
    if not m2:
        raise RuntimeError(f"Invalid gallery URL: {url}")
    host = _extract_host(default_base_url)
    gid = int(m2.group(1))
    token = m2.group(2)
    return gid, token, f"https://{host}/g/{gid}/{token}/"


def _extract_gallery_urls(page_html: str, base_url: str) -> list[str]:
    out: list[str] = []
    seen: set[tuple[int, str]] = set()
    host = _extract_host(base_url)

    # Absolute links first.
    for m in ABS_GALLERY_RE.finditer(page_html):
        abs_host = m.group(1).lower()
        gid = int(m.group(2))
        token = m.group(3)
        key = (gid, token)
        if key in seen:
            continue
        seen.add(key)
        out.append(f"https://{abs_host}/g/{gid}/{token}/")

    # Then relative links (if any remain unseen).
    for m in GALLERY_RE.finditer(page_html):
        gid = int(m.group(1))
        token = m.group(2)
        key = (gid, token)
        if key in seen:
            continue
        seen.add(key)
        out.append(f"https://{host}/g/{gid}/{token}/")

    return out


def _load_state(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(obj, dict):
            return obj
    except Exception:
        pass
    return {}


def _save_state(path: Path, state: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def _load_existing_queue_keys(path: Path) -> set[tuple[int, str]]:
    keys: set[tuple[int, str]] = set()
    if not path.exists():
        return keys
    for line in path.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        try:
            gid, token, _ = _parse_gallery_url(s)
            keys.add((gid, token))
        except Exception:
            continue
    return keys


def _append_queue(path: Path, urls: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        for u in urls:
            f.write(u)
            f.write("\n")


def _sparse_sample(urls: list[str], density: float) -> list[str]:
    if not urls:
        return []
    d = max(0.0, min(1.0, float(density)))
    if d <= 0.0:
        return []
    if d >= 1.0:
        return list(urls)

    n = len(urls)
    keep_n = max(1, int(math.ceil(n * d)))
    if keep_n >= n:
        return list(urls)

    # Evenly sample across newest->older sequence to preserve temporal coverage.
    picked_idx: set[int] = set()
    for i in range(keep_n):
        idx = int(round(i * (n - 1) / (keep_n - 1))) if keep_n > 1 else 0
        picked_idx.add(max(0, min(n - 1, idx)))
    return [u for i, u in enumerate(urls) if i in picked_idx]


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="Fetch new EH gallery URLs incrementally")
    ap.add_argument("--base-url", default="https://e-hentai.org", help="EH listing base URL")
    ap.add_argument("--start-page", type=int, default=0, help="Listing page index to start from")
    ap.add_argument("--max-pages", type=int, default=8, help="How many listing pages to crawl per run")
    ap.add_argument("--timeout", type=int, default=30, help="HTTP timeout seconds")
    ap.add_argument("--sleep-seconds", type=float, default=4.0, help="Sleep seconds between EH requests")
    ap.add_argument(
        "--max-run-minutes",
        type=float,
        default=0.0,
        help="Max runtime minutes for this fetch run (0 means no runtime limit)",
    )
    ap.add_argument(
        "--sampling-density",
        type=float,
        default=1.0,
        help="0.0-1.0 sparse sampling density for queued URLs (1.0 means keep all, 0.0 means keep none)",
    )
    ap.add_argument("--cookie", default="", help="Optional Cookie header")
    ap.add_argument("--user-agent", default="Mozilla/5.0", help="HTTP User-Agent")
    ap.add_argument(
        "--state-file",
        default=str(Path(__file__).resolve().parent / "cache" / "eh_incremental_state.json"),
        help="Checkpoint state file path",
    )
    ap.add_argument(
        "--queue-file",
        default=str(Path(__file__).resolve().parent / "eh_gallery_queue.txt"),
        help="Queue file path (one gallery URL per line)",
    )
    ap.add_argument("--reset-state", action="store_true", help="Ignore previous checkpoint and fetch all pages this run")
    args = ap.parse_args(argv)

    density = max(0.0, min(1.0, float(args.sampling_density)))

    state_path = Path(args.state_file)
    queue_path = Path(args.queue_file)

    state = {} if args.reset_state else _load_state(state_path)
    checkpoint_gid = state.get("last_seen_gid")
    checkpoint_token = state.get("last_seen_token")
    if not isinstance(checkpoint_gid, int):
        checkpoint_gid = None
    if not isinstance(checkpoint_token, str):
        checkpoint_token = None

    existing_keys = _load_existing_queue_keys(queue_path)

    session = requests.Session()
    session.headers.update({"User-Agent": args.user_agent})
    if args.cookie.strip():
        session.headers.update({"Cookie": args.cookie.strip()})

    discovered_new: list[str] = []
    discovered_new_keys: set[tuple[int, str]] = set()
    newest_seen: tuple[int, str] | None = None
    stop_reached = False
    pages_crawled = 0
    sleep_s = max(0.0, float(args.sleep_seconds))
    max_run_s = max(0.0, float(args.max_run_minutes)) * 60.0
    started = time.monotonic()
    stop_reason = "max_pages"

    # Explicit "pause mode": do not crawl and do not move checkpoint.
    if density <= 0.0:
        now = dt.datetime.now(tz=dt.timezone.utc).isoformat()
        state["updated_at"] = now
        state["sampling_density"] = density
        state["last_run_new_count"] = 0
        state["last_run_sampled_count"] = 0
        state["last_run_pages_crawled"] = 0
        state["stop_reached_checkpoint"] = False
        state["checkpoint_advanced"] = False
        _save_state(state_path, state)
        print("Done. sampling_density=0, skipped crawling and queue append.", file=sys.stderr)
        return 0

    start_page = max(0, int(args.start_page))
    max_pages = int(args.max_pages)
    if max_pages <= 0:
        max_pages = 1_000_000
    page_end = start_page + max_pages

    for page in range(start_page, page_end):
        elapsed = time.monotonic() - started
        if max_run_s > 0 and elapsed >= max_run_s:
            stop_reason = "max_run_minutes"
            break

        if pages_crawled > 0 and sleep_s > 0:
            if max_run_s > 0 and (time.monotonic() - started + sleep_s) >= max_run_s:
                stop_reason = "max_run_minutes"
                break
            time.sleep(sleep_s)

        url = f"{args.base_url.rstrip('/')}/?page={page}"
        r = session.get(url, timeout=args.timeout)
        r.raise_for_status()
        pages_crawled += 1

        gallery_urls = _extract_gallery_urls(r.text, args.base_url)
        if not gallery_urls:
            continue

        for u in gallery_urls:
            gid, token, normalized = _parse_gallery_url(u)
            key = (gid, token)

            if newest_seen is None:
                newest_seen = key

            if checkpoint_gid is not None and checkpoint_token is not None and key == (checkpoint_gid, checkpoint_token):
                stop_reached = True
                stop_reason = "checkpoint"
                break

            if key in existing_keys or key in discovered_new_keys:
                continue

            discovered_new_keys.add(key)
            discovered_new.append(normalized)

        if stop_reached:
            break

    sampled_new = _sparse_sample(discovered_new, density)
    if sampled_new:
        _append_queue(queue_path, sampled_new)

    now = dt.datetime.now(tz=dt.timezone.utc).isoformat()
    checkpoint_advanced = False
    can_advance = checkpoint_gid is None or checkpoint_token is None or stop_reached
    if newest_seen is not None and can_advance:
        state["last_seen_gid"] = newest_seen[0]
        state["last_seen_token"] = newest_seen[1]
        checkpoint_advanced = True
    state["updated_at"] = now
    state["sampling_density"] = density
    state["last_run_new_count"] = len(discovered_new)
    state["last_run_sampled_count"] = len(sampled_new)
    state["last_run_pages_crawled"] = pages_crawled
    state["stop_reached_checkpoint"] = stop_reached
    state["stop_reason"] = stop_reason
    state["max_run_minutes"] = float(args.max_run_minutes)
    state["checkpoint_advanced"] = checkpoint_advanced
    state["checkpoint_not_reached"] = bool(checkpoint_gid is not None and checkpoint_token is not None and not stop_reached)
    _save_state(state_path, state)

    print(
        f"Done. new_urls={len(discovered_new)} sampled_urls={len(sampled_new)} density={density:.3f} "
        f"pages_crawled={pages_crawled} checkpoint_reached={stop_reached} "
        f"checkpoint_advanced={checkpoint_advanced} stop_reason={stop_reason} queue_file={queue_path}",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
