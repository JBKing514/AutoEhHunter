#!/usr/bin/env python3
"""Export LANraragi archive metadata via HTTP API.

This script runs outside the container and only needs network access to LANraragi.

It paginates through /api/search and writes JSONL (one JSON object per line)
containing archive id/title/tags and timestamp-like fields.

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
    # Matches tags like: timestamp:1700000000 or date_added:1700000000
    # Also supports Chinese variants used by some plugins: 时间戳:1700000000
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
    req.add_header("User-Agent", "lrr-export/1.0")
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


def export_all(
    base_url: str,
    out_path: str,
    apikey: str | None,
    timeout: float,
    sleep_s: float,
    include_raw_tags: bool,
    filter_expr: str,
) -> None:
    start = 0
    total = None
    written = 0

    # Full refresh: write to a temp file first, then atomically replace the target.
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    tmp_path = out_path + ".tmp"

    with open(tmp_path, "w", encoding="utf-8", newline="\n") as f:
        while True:
            params = {
                "filter": filter_expr,
                "start": str(start),
                "sortby": "title",
                "order": "asc",
            }
            url = base_url + "/api/search?" + urllib.parse.urlencode(params)
            payload = _http_get_json(url, apikey=apikey, timeout=timeout)

            if not isinstance(payload, dict) or "data" not in payload:
                raise RuntimeError(f"Unexpected response format from {url}")

            data = payload.get("data")
            if not isinstance(data, list):
                raise RuntimeError(f"Unexpected data format from {url}")

            if total is None:
                total = int(payload.get("recordsFiltered") or payload.get("recordsTotal") or 0)
                print(f"Total archives (filtered): {total}", file=sys.stderr)

            if not data:
                break

            for arc in data:
                if not isinstance(arc, dict):
                    continue
                arcid = arc.get("arcid")
                title = arc.get("title")
                tags_raw = arc.get("tags") or ""
                lastreadtime = int(arc.get("lastreadtime") or 0)

                tags_list = _split_tags(str(tags_raw))

                # Timestamp-like fields
                eh_posted_epoch = _extract_epoch_tag(tags_list, ["timestamp:", "时间戳:"])
                date_added_epoch = _extract_epoch_tag(tags_list, ["date_added:"])

                row = {
                    "arcid": arcid,
                    "title": title,
                    "tags": tags_list,
                    "lastreadtime": lastreadtime,
                    "lastreadtime_iso": _iso_utc_from_epoch(lastreadtime),
                    "eh_posted": eh_posted_epoch,
                    "eh_posted_iso": _iso_utc_from_epoch(eh_posted_epoch),
                    "date_added": date_added_epoch,
                    "date_added_iso": _iso_utc_from_epoch(date_added_epoch),
                }
                if include_raw_tags:
                    row["tags_raw"] = str(tags_raw)

                f.write(json.dumps(row, ensure_ascii=False) + "\n")
                written += 1

            start += len(data)
            if total is not None:
                print(f"Exported {written}/{total}...", file=sys.stderr)

            if sleep_s > 0:
                time.sleep(sleep_s)

        f.flush()
        try:
            os.fsync(f.fileno())
        except Exception:
            # Not critical; best-effort durability.
            pass

    os.replace(tmp_path, out_path)
    print(f"Wrote {written} rows to {out_path}", file=sys.stderr)


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(
        description="Export LANraragi archive title/tags/timestamps to JSONL using the HTTP API.",
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
        help="LANraragi API key (used for Authorization: Bearer <base64(key)>)",
    )
    p.add_argument(
        "--out",
        default="",
        help="Output JSONL path (default: lanraragi_export.jsonl). Existing file will be replaced.",
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

    args = p.parse_args(argv)

    base_url = _build_base_url(args.ip, args.port, args.scheme, args.base_path)
    apikey = args.apikey.strip() or None

    out_path = args.out
    if not out_path:
        out_path = "lanraragi_export.jsonl"

    try:
        export_all(
            base_url=base_url,
            out_path=out_path,
            apikey=apikey,
            timeout=args.timeout,
            sleep_s=args.sleep,
            include_raw_tags=args.include_raw_tags,
            filter_expr=args.filter,
        )
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
