#!/usr/bin/env python3
"""Export recently-read LANraragi archives via HTTP API.

LANraragi does not keep a full per-session reading event log by default.
What it *does* track is an archive-level "lastreadtime" (epoch seconds),
updated when the reader progress endpoint is called.

This script exports archives whose lastreadtime falls within the last N hours
(default: 24h), including title/tags and timestamp-like fields extracted from tags.

API endpoint used:
  GET /api/search?sortby=lastread&order=desc&start=0
We page forward until lastreadtime is older than the cutoff.

Auth:
  If your LANraragi instance protects APIs, pass --apikey.
  LANraragi expects: Authorization: Bearer <base64(apikey)>
"""

from __future__ import annotations

import argparse
import base64
import datetime as _dt
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request


def _iso_utc_from_epoch(seconds: int) -> str | None:
    if not seconds:
        return None
    try:
        return _dt.datetime.fromtimestamp(int(seconds), tz=_dt.timezone.utc).isoformat()
    except Exception:
        return None


def _split_tags(tags: str) -> list[str]:
    if not tags:
        return []
    out: list[str] = []
    for part in tags.split(","):
        t = part.strip()
        if t:
            out.append(t)
    return out


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


def _http_get_json(url: str, apikey: str | None, timeout: float) -> object:
    req = urllib.request.Request(url, method="GET")
    req.add_header("Accept", "application/json")
    req.add_header("User-Agent", "lrr-recent-reads/1.0")
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

    try:
        return json.loads(raw.decode("utf-8"))
    except Exception as e:
        raise RuntimeError(f"Failed to decode JSON from {url}: {e}")


def _build_base_url(ip: str, port: int, scheme: str, base_path: str) -> str:
    base_path = base_path.strip()
    if base_path and not base_path.startswith("/"):
        base_path = "/" + base_path
    base_path = base_path.rstrip("/")
    return f"{scheme}://{ip}:{port}{base_path}"


def export_recent_reads(
    base_url: str,
    out_path: str,
    apikey: str | None,
    timeout: float,
    sleep_s: float,
    hours: float,
    include_raw_tags: bool,
    filter_expr: str,
    include_tanks: bool,
) -> str:
    now = int(time.time())
    cutoff = int(now - (hours * 3600))

    start = 0
    written = 0
    skipped_tanks = 0
    scanned = 0

    ts = _dt.datetime.now(tz=_dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    resolved_out = out_path.replace("{timestamp}", ts)

    resolved_out = resolved_out.replace("{", "").replace("}", "")
    if resolved_out.endswith(".jsonl.jsonl"):
        resolved_out = resolved_out[: -len(".jsonl")]  # keep one .jsonl

    os.makedirs(os.path.dirname(resolved_out) or ".", exist_ok=True)
    tmp_path = resolved_out + ".tmp"

    with open(tmp_path, "w", encoding="utf-8", newline="\n") as f:
        while True:
            params = {
                "filter": filter_expr,
                "start": str(start),
                "sortby": "lastread",
                "order": "asc",
            }
            url = base_url + "/api/search?" + urllib.parse.urlencode(params)
            payload = _http_get_json(url, apikey=apikey, timeout=timeout)

            if not isinstance(payload, dict) or "data" not in payload:
                raise RuntimeError(f"Unexpected response format from {url}")

            data = payload.get("data")
            if not isinstance(data, list):
                raise RuntimeError(f"Unexpected data format from {url}")

            if not data:
                break

            stop = False
            for arc in data:
                if not isinstance(arc, dict):
                    continue
                scanned += 1
                
                #print(f"DEBUG: Title={arc.get('title')}, LastRead={arc.get('lastreadtime')}, Cutoff={cutoff}", file=sys.stderr)

                arcid = arc.get("arcid")
                if (not include_tanks) and isinstance(arcid, str) and arcid.startswith("TANK"):
                    skipped_tanks += 1
                    continue

                lastreadtime = int(arc.get("lastreadtime") or 0)
                if lastreadtime < cutoff:
                    stop = True
                    break

                title = arc.get("title")
                tags_raw = arc.get("tags") or ""
                tags_list = _split_tags(str(tags_raw))

                eh_posted_epoch = _extract_epoch_tag(tags_list, ["timestamp:", "时间戳:"])
                date_added_epoch = _extract_epoch_tag(tags_list, ["date_added:"])

                row = {
                    "arcid": arcid,
                    "title": title,
                    "tags": tags_list,
                    "read_time": lastreadtime,
                    "read_time_iso": _iso_utc_from_epoch(lastreadtime),
                    "cutoff": cutoff,
                    "cutoff_iso": _iso_utc_from_epoch(cutoff),
                    "eh_posted": eh_posted_epoch,
                    "eh_posted_iso": _iso_utc_from_epoch(eh_posted_epoch),
                    "date_added": date_added_epoch,
                    "date_added_iso": _iso_utc_from_epoch(date_added_epoch),
                }
                if include_raw_tags:
                    row["tags_raw"] = str(tags_raw)

                f.write(json.dumps(row, ensure_ascii=False) + "\n")
                written += 1

            if stop:
                break

            start += len(data)
            if sleep_s > 0:
                time.sleep(sleep_s)

        f.flush()
        try:
            os.fsync(f.fileno())
        except Exception:
            pass

    os.replace(tmp_path, resolved_out)
    print(
        f"Wrote {written} rows to {resolved_out} (cutoff={cutoff} / { _iso_utc_from_epoch(cutoff) }, scanned={scanned}, skipped_tanks={skipped_tanks})",
        file=sys.stderr,
    )

    if written == 0 and skipped_tanks > 0 and not include_tanks:
        print(
            "Hint: all recent rows may be TANK entries. Set --include-tanks (or LRR_READS_INCLUDE_TANKS=1).",
            file=sys.stderr,
        )

    return resolved_out


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(
        description="Export archives read within the last N hours from LANraragi (based on lastreadtime).",
    )
    p.add_argument("--ip", required=True, help="LANraragi server IP or hostname")
    p.add_argument("--port", required=True, type=int, help="LANraragi server port")
    p.add_argument("--scheme", default="http", choices=["http", "https"], help="URL scheme")
    p.add_argument(
        "--base-path",
        default="",
        help="Optional base URL prefix (example: /lanraragi)",
    )
    p.add_argument(
        "--apikey",
        default="",
        help="LANraragi API key (Authorization: Bearer <base64(key)>)",
    )
    p.add_argument(
        "--out",
        default="lrr_reads_last24h.jsonl",
        help=(
            "Output JSONL path template. Use {timestamp} for UTC timestamp. "
            "Example: exports/daily/lrr_reads_{timestamp}.jsonl"
        ),
    )
    p.add_argument(
        "--hours",
        type=float,
        default=24.0,
        help="Lookback window in hours (default: 24)",
    )
    p.add_argument(
        "--sleep",
        type=float,
        default=0.0,
        help="Sleep seconds between pages (0 to disable)",
    )
    p.add_argument(
        "--timeout",
        type=float,
        default=30.0,
        help="HTTP timeout seconds",
    )
    p.add_argument(
        "--include-raw-tags",
        action="store_true",
        help="Include tags_raw as returned by LANraragi",
    )
    p.add_argument(
        "--filter",
        default="",
        help="LANraragi search filter expression (default: empty = all archives)",
    )
    p.add_argument(
        "--include-tanks",
        action="store_true",
        help="Include tank entries (TANK...) if they appear in results",
    )

    args = p.parse_args(argv)

    base_url = _build_base_url(args.ip, args.port, args.scheme, args.base_path)
    apikey = args.apikey.strip() or None

    try:
        export_recent_reads(
            base_url=base_url,
            out_path=args.out,
            apikey=apikey,
            timeout=args.timeout,
            sleep_s=args.sleep,
            hours=args.hours,
            include_raw_tags=args.include_raw_tags,
            filter_expr=args.filter,
            include_tanks=args.include_tanks,
        )
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
