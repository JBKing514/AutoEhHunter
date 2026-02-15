#!/usr/bin/env python3
"""LANraragi -> VLM description + embeddings -> Postgres (pgvector)

Pipeline per arcid:
  - Fetch cover + 3 random pages from LANraragi Archive API
  - Send images to a local OpenAI-compatible VLM (llama.cpp llama-server)
  - Embed the resulting description text using a local embedding server (bge-m3)
  - Compute a visual embedding using SigLIP (transformers)
  - Write back: works.description, works.desc_embedding, works.visual_embedding

This is designed to run on your Ubuntu worker box.

Dependencies:
  pip install "psycopg[binary]" requests python-dotenv torch torchvision transformers pillow
"""

from __future__ import annotations

import argparse
import base64
import io
import json
import os
import random
import sys
import tempfile
import time
import uuid
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import parse_qs, unquote, urlparse

import requests
from requests import exceptions as req_exc


def _env_bool(name: str, default: bool = False) -> bool:
    v = os.getenv(name)
    if v is None:
        return default
    return v.strip().lower() in ("1", "true", "yes", "y", "on")


def _b64(s: str) -> str:
    return base64.b64encode(s.encode("utf-8")).decode("ascii")


def _vector_literal(vec: list[float]) -> str:
    # pgvector accepts: '[1,2,3]'
    # Keep it compact; avoid scientific notation pitfalls by using repr.
    return "[" + ",".join(repr(float(x)) for x in vec) + "]"


def _is_retryable_http_status(status_code: int) -> bool:
    return status_code in (408, 425, 429, 500, 502, 503, 504)


def _is_retryable_request_error(exc: Exception) -> bool:
    if isinstance(exc, (req_exc.Timeout, req_exc.ConnectionError)):
        return True
    if isinstance(exc, req_exc.HTTPError):
        r = exc.response
        return r is not None and _is_retryable_http_status(int(r.status_code))
    return False


def _request_with_retry(
    *,
    method: str,
    url: str,
    timeout_s: int,
    max_attempts: int,
    retry_base_s: float,
    retry_max_s: float,
    request_name: str,
    warn: bool = True,
    **kwargs: Any,
) -> requests.Response:
    attempts = max(1, int(max_attempts))
    base = max(0.0, float(retry_base_s))
    cap = max(base, float(retry_max_s))
    last_err: Exception | None = None

    for attempt in range(1, attempts + 1):
        try:
            resp = requests.request(method, url, timeout=timeout_s, **kwargs)
            if _is_retryable_http_status(resp.status_code):
                if attempt >= attempts:
                    return resp
                wait_s = min(cap, base * (2 ** (attempt - 1)))
                if warn:
                    print(
                        f"WARN {request_name} HTTP {resp.status_code}, retry {attempt}/{attempts} in {wait_s:.1f}s",
                        file=sys.stderr,
                    )
                time.sleep(wait_s)
                continue
            return resp
        except Exception as e:
            last_err = e
            if not _is_retryable_request_error(e) or attempt >= attempts:
                raise
            wait_s = min(cap, base * (2 ** (attempt - 1)))
            if warn:
                print(
                    f"WARN {request_name} {type(e).__name__}: {e}; retry {attempt}/{attempts} in {wait_s:.1f}s",
                    file=sys.stderr,
                )
            time.sleep(wait_s)

    if last_err is not None:
        raise last_err
    raise RuntimeError(f"{request_name} failed without response")


def _connect_db_with_retry(
    psycopg_mod: Any,
    dsn: str,
    *,
    max_attempts: int,
    retry_base_s: float,
    retry_max_s: float,
) -> Any:
    attempts = max(1, int(max_attempts))
    base = max(0.0, float(retry_base_s))
    cap = max(base, float(retry_max_s))
    last_err: Exception | None = None

    for attempt in range(1, attempts + 1):
        try:
            return psycopg_mod.connect(dsn)
        except Exception as e:
            last_err = e
            if attempt >= attempts:
                raise
            wait_s = min(cap, base * (2 ** (attempt - 1)))
            print(
                f"WARN db.connect {type(e).__name__}: {e}; retry {attempt}/{attempts} in {wait_s:.1f}s",
                file=sys.stderr,
            )
            time.sleep(wait_s)

    if last_err is not None:
        raise last_err
    raise RuntimeError("db.connect failed without exception")


@dataclass
class LrrClient:
    base_url: str
    auth_bearer: str | None
    timeout_s: int = 120
    retry_attempts: int = 4
    retry_base_s: float = 1.0
    retry_max_s: float = 20.0

    def _headers(self) -> dict[str, str]:
        h = {"Accept": "application/json"}
        if self.auth_bearer:
            h["Authorization"] = f"Bearer {self.auth_bearer}"
        return h

    def get_archive_pages(self, arcid: str) -> list[str]:
        url = f"{self.base_url.rstrip('/')}/api/archives/{arcid}/files"
        r = _request_with_retry(
            method="GET",
            url=url,
            timeout_s=self.timeout_s,
            max_attempts=self.retry_attempts,
            retry_base_s=self.retry_base_s,
            retry_max_s=self.retry_max_s,
            request_name=f"lrr.get_archive_pages arcid={arcid}",
            headers=self._headers(),
        )
        r.raise_for_status()
        obj = r.json()
        pages = obj.get("pages") or []
        out: list[str] = []
        for p in pages:
            if not isinstance(p, str):
                continue
            # Example: "./api/archives/<id>/page&path=00.jpg"
            p2 = p.lstrip("./")
            out.append(f"{self.base_url.rstrip('/')}/{p2}")
        return out

    def get_thumbnail(self, arcid: str, page: int | None = None) -> bytes:
        url = f"{self.base_url.rstrip('/')}/api/archives/{arcid}/thumbnail"
        params = {}
        if page is not None:
            params["page"] = str(page)
        r = _request_with_retry(
            method="GET",
            url=url,
            timeout_s=self.timeout_s,
            max_attempts=self.retry_attempts,
            retry_base_s=self.retry_base_s,
            retry_max_s=self.retry_max_s,
            request_name=f"lrr.get_thumbnail arcid={arcid}",
            headers={k: v for k, v in self._headers().items() if k != "Accept"},
            params=params,
        )
        r.raise_for_status()
        return r.content

    def download_bytes(self, url: str) -> bytes:
        r = _request_with_retry(
            method="GET",
            url=url,
            timeout_s=self.timeout_s,
            max_attempts=self.retry_attempts,
            retry_base_s=self.retry_base_s,
            retry_max_s=self.retry_max_s,
            request_name=f"lrr.download_bytes {url}",
            headers={k: v for k, v in self._headers().items() if k != "Accept"},
        )
        r.raise_for_status()
        return r.content


@dataclass
class OpenAICompatClient:
    base_url: str
    api_key: str | None = None
    timeout_s: int = 120
    retry_attempts: int = 4
    retry_base_s: float = 1.0
    retry_max_s: float = 20.0

    def _headers(self) -> dict[str, str]:
        h = {"Content-Type": "application/json"}
        if self.api_key:
            h["Authorization"] = f"Bearer {self.api_key}"
        return h

    def chat_completions(self, model: str, messages: list[dict[str, Any]], temperature: float = 0.2, max_tokens: int = 800) -> str:
        url = f"{self.base_url.rstrip('/')}/v1/chat/completions"
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        r = _request_with_retry(
            method="POST",
            url=url,
            timeout_s=self.timeout_s,
            max_attempts=self.retry_attempts,
            retry_base_s=self.retry_base_s,
            retry_max_s=self.retry_max_s,
            request_name=f"vl.chat_completions model={model}",
            warn=False,
            headers=self._headers(),
            json=payload,
        )
        if r.status_code >= 400:
            body = r.text
            if len(body) > 4000:
                body = body[:4000] + "..."
            raise RuntimeError(f"VLM HTTP {r.status_code} for {url}: {body}")
        obj = r.json()
        choices = obj.get("choices") or []
        if not choices:
            raise RuntimeError(f"No choices in response: keys={list(obj.keys())}")
        msg = (choices[0] or {}).get("message") or {}
        content = msg.get("content")
        if isinstance(content, str):
            return content
        # Some servers return structured content
        if isinstance(content, list):
            parts = []
            for p in content:
                if isinstance(p, dict) and isinstance(p.get("text"), str):
                    parts.append(p["text"])
            if parts:
                return "\n".join(parts)
        raise RuntimeError("Unexpected chat completion payload")

    def embeddings(self, model: str, text: str) -> list[float]:
        url = f"{self.base_url.rstrip('/')}/v1/embeddings"
        payload = {"model": model, "input": text}
        r = _request_with_retry(
            method="POST",
            url=url,
            timeout_s=self.timeout_s,
            max_attempts=self.retry_attempts,
            retry_base_s=self.retry_base_s,
            retry_max_s=self.retry_max_s,
            request_name=f"emb.embeddings model={model}",
            warn=False,
            headers=self._headers(),
            json=payload,
        )
        if r.status_code >= 400:
            body = r.text
            if len(body) > 4000:
                body = body[:4000] + "..."
            raise RuntimeError(f"Embedding HTTP {r.status_code} for {url}: {body}")
        obj = r.json()
        data = obj.get("data") or []
        if not data:
            raise RuntimeError(f"No embedding data in response: keys={list(obj.keys())}")
        emb = data[0].get("embedding")
        if not isinstance(emb, list):
            raise RuntimeError("Embedding is not a list")
        return [float(x) for x in emb]


class SiglipEncoder:
    def __init__(self, model_name: str, device: str, cuda_visible_devices: str | None = None):
        # IMPORTANT: if you want SigLIP to run on a specific physical GPU,
        # set cuda_visible_devices (or export CUDA_VISIBLE_DEVICES) BEFORE importing torch.
        if cuda_visible_devices is not None and str(cuda_visible_devices).strip():
            cvd = str(cuda_visible_devices).strip()
            os.environ["CUDA_VISIBLE_DEVICES"] = cvd
            # If we expose a single GPU, inside-process indexing becomes cuda:0.
            if "," not in cvd and device.startswith("cuda:") and device != "cuda:0":
                device = "cuda:0"

        import torch
        from transformers import AutoModel, AutoProcessor

        self.torch = torch
        self.device = device

        torch_dtype = None
        if device.startswith("cuda") and torch.cuda.is_available():
            torch_dtype = torch.float16

        # AutoModel works, but output shapes vary across transformers versions.
        # We handle both tensor and BaseModelOutputWithPooling below.
        self.model = AutoModel.from_pretrained(
            model_name,
            torch_dtype=torch_dtype,
            low_cpu_mem_usage=True,
        ).to(device)
        self.processor = AutoProcessor.from_pretrained(model_name)
        self.model.eval()

    def embed_image_path(self, image_path: str) -> list[float]:
        from PIL import Image

        image = Image.open(image_path).convert("RGB")
        inputs = self.processor(images=image, return_tensors="pt")
        inputs = {k: v.to(self.device) for k, v in inputs.items()}
        with self.torch.no_grad():
            out: Any
            if hasattr(self.model, "get_image_features"):
                out = self.model.get_image_features(**inputs)
            else:
                out = self.model(**inputs)

            # Some versions return a Tensor, others return an output object.
            if isinstance(out, self.torch.Tensor):
                feats = out
            elif hasattr(out, "pooler_output") and out.pooler_output is not None:
                feats = out.pooler_output
            elif isinstance(out, dict) and "image_embeds" in out:
                feats = out["image_embeds"]
            else:
                raise RuntimeError(f"Unexpected SigLIP output type: {type(out)}")
        feats = feats / feats.norm(p=2, dim=-1, keepdim=True)
        return feats.detach().cpu().numpy().astype("float32").tolist()[0]


def _l2_normalize(vec: list[float]) -> list[float]:
    s = 0.0
    for x in vec:
        s += float(x) * float(x)
    if s <= 0.0:
        return vec
    inv = s ** -0.5
    return [float(x) * inv for x in vec]


def _sniff_image_ext_and_mime(b: bytes) -> tuple[str, str]:
    if b.startswith(b"\x89PNG\r\n\x1a\n"):
        return ".png", "image/png"
    if b[:2] == b"BM":
        return ".bmp", "image/bmp"
    if b[:4] == b"RIFF" and b[8:12] == b"WEBP":
        return ".webp", "image/webp"
    # Default to jpeg.
    return ".jpg", "image/jpeg"


def _normalize_to_jpeg_bytes(b: bytes) -> bytes:
    """Decode image bytes and re-encode as JPEG.

    This avoids server-side decoder limitations (e.g. WEBP) and keeps inputs uniform.
    """

    from PIL import Image

    img = Image.open(io.BytesIO(b))
    # Ensure RGB (JPEG has no alpha)
    if img.mode not in ("RGB", "L"):
        img = img.convert("RGB")
    elif img.mode == "L":
        img = img.convert("RGB")

    out = io.BytesIO()
    img.save(out, format="JPEG", quality=92, optimize=True)
    return out.getvalue()


def _make_vlm_messages_file(
    description_instruction: str,
    image_blobs: list[bytes],
    *,
    media_dir: Path,
    arcid: str,
    url_prefix: str,
) -> tuple[list[dict[str, Any]], Path]:
    """Write images under media_dir and reference them with file:// relative URLs.

    The returned subdir should be cleaned up after the request.
    """

    parts: list[dict[str, Any]] = [{"type": "text", "text": description_instruction}]
    subdir = media_dir / f"{arcid}_{uuid.uuid4().hex[:8]}"
    subdir.mkdir(parents=True, exist_ok=True)

    for i, b in enumerate(image_blobs):
        # Use JPEG to maximize decoder compatibility.
        rel = Path(subdir.name) / f"img_{i:02d}.jpg"
        (media_dir / rel).write_bytes(b)
        parts.append({"type": "image_url", "image_url": {"url": f"{url_prefix}{rel.as_posix()}"}})

    return ([{"role": "user", "content": parts}], subdir)


def _make_vlm_messages_from_urls(description_instruction: str, urls: list[str]) -> list[dict[str, Any]]:
    parts: list[dict[str, Any]] = [{"type": "text", "text": description_instruction}]
    for u in urls:
        parts.append({"type": "image_url", "image_url": {"url": u}})
    return [{"role": "user", "content": parts}]


def _vl_messages_from_existing_dir(
    description_instruction: str,
    *,
    media_dir: Path,
    subdir: Path,
    url_prefix: str,
) -> list[dict[str, Any]]:
    parts: list[dict[str, Any]] = [{"type": "text", "text": description_instruction}]
    # Files are inside subdir; generate URLs relative to media_dir.
    rel_base = Path(subdir.name)
    for p in sorted(subdir.iterdir()):
        if not p.is_file():
            continue
        rel = rel_base / p.name
        parts.append({"type": "image_url", "image_url": {"url": f"{url_prefix}{rel.as_posix()}"}})
    return [{"role": "user", "content": parts}]


def _abs_file_uri(abs_posix_path: str) -> str:
    # file URI should be file:///abs/path
    if not abs_posix_path.startswith("/"):
        abs_posix_path = "/" + abs_posix_path
    return "file:///" + abs_posix_path.lstrip("/")


def _try_vlm_with_dir(
    vl: OpenAICompatClient,
    *,
    model: str,
    instruction: str,
    images_dir: Path,
    preferred_prefix: str,
) -> str:
    files = [p for p in sorted(images_dir.iterdir()) if p.is_file()]
    if not files:
        raise RuntimeError("No image files written for VLM")

    # Paths relative to media root.
    rels = [f"{images_dir.name}/{p.name}" for p in files]
    abss = [p.resolve().as_posix() for p in files]

    # Candidate URL lists to try in order.
    candidates: list[tuple[str, list[str]]] = []

    def add_prefix(prefix: str) -> None:
        if prefix == "":
            candidates.append(("rel", rels))
        elif prefix in ("file://", "file:"):
            candidates.append((prefix, [prefix + r for r in rels]))

    # Try user-preferred first.
    add_prefix(preferred_prefix)
    # Then common variants.
    for pfx in ("file://", "file:", ""):
        if pfx != preferred_prefix:
            add_prefix(pfx)

    # Absolute path variants.
    candidates.append(("abs_file_uri", [_abs_file_uri(a) for a in abss]))
    candidates.append(("abs_path", abss))
    candidates.append(("file_abs", ["file:" + a for a in abss]))

    debug = _env_bool("VL_DEBUG_URLS", False)
    last_err: Exception | None = None
    for label, urls in candidates:
        try:
            if debug:
                sample = urls[0] if urls else ""
                print(f"VLM url_style={label} sample={sample}")
            msgs = _make_vlm_messages_from_urls(instruction, urls)
            return vl.chat_completions(model=model, messages=msgs, temperature=0.2, max_tokens=900).strip()
        except Exception as e:
            last_err = e
            s = str(e)
            # Retry only for URL/image load issues.
            if "Invalid url value" in s or "Failed to load image" in s:
                continue
            raise

    raise RuntimeError(str(last_err) if last_err else "VLM failed")


def _make_vlm_messages_data_url(
    description_instruction: str, image_blobs: list[bytes]
) -> list[dict[str, Any]]:
    parts: list[dict[str, Any]] = [{"type": "text", "text": description_instruction}]
    for b in image_blobs:
        mime = "image/jpeg"
        b64 = base64.b64encode(b).decode("ascii")
        parts.append({"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}})
    return [{"role": "user", "content": parts}]


def _page_filename_from_url(page_url: str) -> str:
    """Extract archive page filename from LANraragi page URL.

    Expected shape:
      /api/archives/<id>/page?path=0001.webp
    """

    try:
        parsed = urlparse(page_url)
        q = parse_qs(parsed.query)
        path_vals = q.get("path") or []
        if path_vals:
            return Path(unquote(path_vals[0])).name
        # Fallback for odd routes that don't use query parameter.
        return Path(unquote(parsed.path)).name
    except Exception:
        return ""


def _page_index_from_filename(filename: str) -> int | None:
    stem = Path(filename).stem
    if stem.isdigit():
        try:
            return int(stem)
        except Exception:
            return None
    return None


def _is_thumb_filename(filename: str) -> bool:
    # LRR often returns a synthetic ".thumb.webp" entry in page list.
    name = filename.lower()
    return name.startswith(".thumb") or "path=.thumb" in name


def _choose_cover_page_url(page_urls: list[str]) -> str | None:
    """Pick cover page from internal pages, preferring index==1.

    Handles names like 1.webp / 0001.webp / 00000001.webp.
    Excludes ".thumb.*".
    """

    candidates: list[tuple[int, str, str]] = []
    fallback: list[str] = []

    for u in page_urls:
        fn = _page_filename_from_url(u)
        if not fn or _is_thumb_filename(fn):
            continue
        fallback.append(u)
        idx = _page_index_from_filename(fn)
        if idx is None:
            continue
        # keep filename for stable tie-breaker
        candidates.append((idx, fn, u))

    if candidates:
        # Priority 1: exact page index 1
        page1 = [x for x in candidates if x[0] == 1]
        if page1:
            page1.sort(key=lambda x: (len(x[1]), x[1]))
            return page1[0][2]
        # Fallback: smallest numeric page index
        candidates.sort(key=lambda x: (x[0], len(x[1]), x[1]))
        return candidates[0][2]

    if fallback:
        # Last fallback: first non-thumb entry as provided by server
        return fallback[0]
    return None


def _pick_images(lrr: LrrClient, arcid: str, rng: random.Random, k_random_pages: int = 3) -> list[bytes]:
    pages = lrr.get_archive_pages(arcid)

    # Use internal page list only (no /thumbnail fallback), and pick cover as page index 1.
    cover_url = _choose_cover_page_url(pages)
    if not cover_url:
        raise RuntimeError(f"No usable pages found for arcid={arcid}")

    blobs: list[bytes] = [lrr.download_bytes(cover_url)]
    #debug: print cover url
    #print(cover_url)

    # Exclude thumb and selected cover, then sample random content pages.
    candidates: list[str] = []
    for u in pages:
        if u == cover_url:
            continue
        fn = _page_filename_from_url(u)
        if not fn or _is_thumb_filename(fn):
            continue
        candidates.append(u)

    if candidates:
        if len(candidates) <= k_random_pages:
            picks = candidates
        else:
            picks = rng.sample(candidates, k=k_random_pages)
        for u in picks:
            blobs.append(lrr.download_bytes(u))

    return blobs


def _iter_arcids_from_args(args: argparse.Namespace) -> Iterable[str]:
    if args.arcid:
        for a in args.arcid:
            a = str(a).strip()
            if a:
                yield a


def main(argv: list[str]) -> int:
    try:
        from dotenv import load_dotenv

        load_dotenv()
    except Exception:
        pass

    ap = argparse.ArgumentParser(description="Generate VLM description + embeddings for LANraragi works")
    ap.add_argument("--dsn", required=True, help="PostgreSQL DSN")
    ap.add_argument("--lrr-base", default=os.getenv("LRR_BASE", "http://127.0.0.1:3000"), help="LANraragi base URL")
    ap.add_argument("--lrr-api-key", default=os.getenv("LRR_API_KEY", ""), help="LANraragi API key (raw, will base64 encode)")
    ap.add_argument("--lrr-api-key-b64", default=os.getenv("LRR_API_KEY_B64", ""), help="LANraragi API key (already base64)")

    ap.add_argument("--vl-base", default=os.getenv("VL_BASE", "http://127.0.0.1:8002"), help="VLM server base URL")
    ap.add_argument("--emb-base", default=os.getenv("EMB_BASE", "http://127.0.0.1:8001"), help="Embedding server base URL")
    ap.add_argument("--vl-model", default=os.getenv("VL_MODEL_ID", "vl"), help="Model id for /v1/chat/completions")
    ap.add_argument("--emb-model", default=os.getenv("EMB_MODEL_ID", "bge-m3"), help="Model id for /v1/embeddings")

    ap.add_argument(
        "--vl-image-mode",
        choices=["file", "data_url"],
        default=os.getenv("VL_IMAGE_MODE", "file"),
        help="How to send images to the VLM server (default: file)",
    )
    ap.add_argument(
        "--vl-normalize-jpeg",
        action="store_true",
        default=_env_bool("VL_NORMALIZE_JPEG", True),
        help="Re-encode all VLM input images as JPEG (default: true)",
    )
    ap.add_argument(
        "--vl-media-dir",
        default=os.getenv("VL_MEDIA_DIR", os.path.expanduser("~/.cache/lrr_worker/media_vl")),
        help="Directory served by llama-server --media-path (used when --vl-image-mode=file)",
    )
    ap.add_argument(
        "--vl-file-url-prefix",
        default=os.getenv("VL_FILE_URL_PREFIX", "file:"),
        help="Prefix used for file URLs (default: file:)",
    )

    ap.add_argument(
        "--vl-keep-media",
        action="store_true",
        default=_env_bool("VL_KEEP_MEDIA", False),
        help="Do not delete temp media files (useful for debugging)",
    )

    ap.add_argument("--siglip-model", default=os.getenv("SIGLIP_MODEL", "google/siglip-so400m-patch14-384"), help="SigLIP HF model name or local path")
    ap.add_argument(
        "--siglip-device",
        default=os.getenv("SIGLIP_DEVICE", "cuda:0"),
        help="Torch device for SigLIP inside this process (default: cuda:0)",
    )
    ap.add_argument(
        "--siglip-cuda-visible-devices",
        default=os.getenv("SIGLIP_CUDA_VISIBLE_DEVICES", "2"),
        help=(
            "Set CUDA_VISIBLE_DEVICES right before importing torch for SigLIP. "
            "Use your physical GPU index here. Default '2' per your host mapping."
        ),
    )
    ap.add_argument("--seed", type=int, default=int(os.getenv("WORKER_SEED", "1337")))
    ap.add_argument("--limit", type=int, default=int(os.getenv("WORKER_LIMIT", "0")), help="Max arcids to process (0 = unlimited)")
    ap.add_argument("--batch", type=int, default=int(os.getenv("WORKER_BATCH", "32")), help="DB update batch size")
    ap.add_argument("--dry-run", action="store_true", default=_env_bool("WORKER_DRY_RUN", False))
    ap.add_argument("--only-missing", action="store_true", default=_env_bool("WORKER_ONLY_MISSING", True), help="Process only rows missing embeddings/description")
    ap.add_argument("--arcid", nargs="*", help="Specific arcid(s) to process")
    ap.add_argument("--sleep", type=float, default=float(os.getenv("WORKER_SLEEP", "0")), help="Sleep seconds between items")
    ap.add_argument(
        "--net-retry-attempts",
        type=int,
        default=int(os.getenv("WORKER_NET_RETRY_ATTEMPTS", "4")),
        help="Retry attempts for LRR/DB transient network errors (default: 4)",
    )
    ap.add_argument(
        "--net-retry-base",
        type=float,
        default=float(os.getenv("WORKER_NET_RETRY_BASE", "1.0")),
        help="Initial retry backoff seconds (default: 1.0)",
    )
    ap.add_argument(
        "--net-retry-max",
        type=float,
        default=float(os.getenv("WORKER_NET_RETRY_MAX", "20.0")),
        help="Max retry backoff seconds (default: 20.0)",
    )

    args = ap.parse_args(argv)

    auth = None
    if args.lrr_api_key_b64.strip():
        auth = args.lrr_api_key_b64.strip()
    elif args.lrr_api_key.strip():
        auth = _b64(args.lrr_api_key.strip())

    lrr = LrrClient(
        base_url=args.lrr_base,
        auth_bearer=auth,
        retry_attempts=args.net_retry_attempts,
        retry_base_s=args.net_retry_base,
        retry_max_s=args.net_retry_max,
    )
    vl = OpenAICompatClient(
        base_url=args.vl_base,
        api_key=os.getenv("OPENAI_API_KEY") or None,
        retry_attempts=1,
        retry_base_s=args.net_retry_base,
        retry_max_s=args.net_retry_max,
    )
    emb = OpenAICompatClient(
        base_url=args.emb_base,
        api_key=os.getenv("OPENAI_API_KEY") or None,
        retry_attempts=1,
        retry_base_s=args.net_retry_base,
        retry_max_s=args.net_retry_max,
    )

    media_dir = Path(args.vl_media_dir)
    if args.vl_image_mode == "file":
        media_dir.mkdir(parents=True, exist_ok=True)

    rng = random.Random(args.seed)

    # Lazy-init SigLIP because it is heavy.
    siglip: SiglipEncoder | None = None

    try:
        import psycopg
    except Exception as e:
        print('Missing psycopg. Install with: pip install "psycopg[binary]"')
        print(str(e))
        return 2

    select_sql = (
        "SELECT arcid FROM works "
        + (
            "WHERE (description IS NULL OR description = '' OR desc_embedding IS NULL OR visual_embedding IS NULL) "
            if args.only_missing
            else ""
        )
        + "ORDER BY arcid"
    )

    arcids: list[str] = list(_iter_arcids_from_args(args))

    with _connect_db_with_retry(
        psycopg,
        args.dsn,
        max_attempts=args.net_retry_attempts,
        retry_base_s=args.net_retry_base,
        retry_max_s=args.net_retry_max,
    ) as conn:
        conn.execute("SET statement_timeout = '10min'")
        if not arcids:
            with conn.cursor() as cur:
                cur.execute(select_sql)
                arcids = [r[0] for r in cur.fetchall()]
        if args.limit and args.limit > 0:
            arcids = arcids[: args.limit]

        print(f"Will process arcids={len(arcids)}")

        pending: list[tuple[str, str, str, str]] = []

        for i, arcid in enumerate(arcids, start=1):
            t0 = time.time()
            try:
                blobs = _pick_images(lrr, arcid, rng=rng, k_random_pages=3)
                if args.vl_normalize_jpeg:
                    norm: list[bytes] = []
                    for b in blobs:
                        try:
                            norm.append(_normalize_to_jpeg_bytes(b))
                        except Exception as e:
                            raise RuntimeError(
                                "Failed to decode/convert an input image to JPEG. "
                                "If your pages are WEBP, ensure Pillow has WEBP support. "
                                f"Original error: {e}"
                            )
                    blobs = norm
                instruction = (
                    "请详细描述这些图片的内容。要求：\n"
                    "- 重点包括：画风、角色外观、动作、服装细节、场景元素、构图、镜头、情绪氛围。\n"
                    "- 尽量客观描述可见内容，不要编造看不见的设定。\n"
                    "- 输出为一段结构化描述（可分句），不要输出多余前后缀。"
                )
                cleanup_dir: Path | None = None
                vl_ok = False
                try:
                    if args.vl_image_mode == "file":
                        messages, cleanup_dir = _make_vlm_messages_file(
                            instruction,
                            blobs,
                            media_dir=media_dir,
                            arcid=arcid,
                            url_prefix=args.vl_file_url_prefix,
                        )
                    else:
                        messages = _make_vlm_messages_data_url(instruction, blobs)

                    if args.vl_image_mode == "file" and cleanup_dir is not None:
                        if _env_bool("VL_DEBUG_URLS", False):
                            files = [p.name for p in sorted(cleanup_dir.iterdir()) if p.is_file()]
                            print(f"VLM media_dir={media_dir} subdir={cleanup_dir.name} files={files}")
                        # The initial message build is only for a fast path; retry logic below
                        # tries multiple URL styles if the server complains.
                        description = _try_vlm_with_dir(
                            vl,
                            model=args.vl_model,
                            instruction=instruction,
                            images_dir=cleanup_dir,
                            preferred_prefix=args.vl_file_url_prefix,
                        )
                    else:
                        description = vl.chat_completions(
                            model=args.vl_model,
                            messages=messages,
                            temperature=0.2,
                            max_tokens=900,
                        ).strip()
                    vl_ok = True
                finally:
                    if cleanup_dir is not None and (not args.vl_keep_media) and vl_ok:
                        shutil.rmtree(cleanup_dir, ignore_errors=True)
                if not description:
                    raise RuntimeError("Empty description")

                semantic = emb.embeddings(model=args.emb_model, text=description)

                if siglip is None:
                    siglip = SiglipEncoder(
                        model_name=args.siglip_model,
                        device=args.siglip_device,
                        cuda_visible_devices=args.siglip_cuda_visible_devices,
                    )

                # Visual embedding: average over sampled images, then L2 normalize.
                with tempfile.TemporaryDirectory(prefix=f"lrr_{arcid}_") as td:
                    paths: list[str] = []
                    for j, b in enumerate(blobs):
                        p = str(Path(td) / f"img_{j:02d}.jpg")
                        Path(p).write_bytes(b)
                        paths.append(p)
                    vecs = [siglip.embed_image_path(p) for p in paths]
                    dim = len(vecs[0])
                    acc = [0.0] * dim
                    for v in vecs:
                        if len(v) != dim:
                            raise RuntimeError(f"SigLIP dim mismatch: {len(v)} vs {dim}")
                        for k in range(dim):
                            acc[k] += float(v[k])
                    acc = [x / float(len(vecs)) for x in acc]
                    visual = _l2_normalize(acc)

                pending.append(
                    (
                        arcid,
                        description,
                        _vector_literal(semantic),
                        _vector_literal(visual),
                    )
                )

                if not args.dry_run and len(pending) >= args.batch:
                    with conn.cursor() as cur:
                        cur.executemany(
                            "UPDATE works SET description = %s, desc_embedding = %s::vector, visual_embedding = %s::vector WHERE arcid = %s",
                            [(d, s, v, a) for (a, d, s, v) in pending],
                        )
                    conn.commit()
                    pending.clear()

                dt = time.time() - t0
                print(f"[{i}/{len(arcids)}] OK {arcid} ({dt:.2f}s) desc_len={len(description)}")

            except Exception as e:
                dt = time.time() - t0
                print(f"[{i}/{len(arcids)}] ERROR {arcid} ({dt:.2f}s): {e}")

            if args.sleep > 0:
                time.sleep(args.sleep)

        if pending and not args.dry_run:
            with conn.cursor() as cur:
                cur.executemany(
                    "UPDATE works SET description = %s, desc_embedding = %s::vector, visual_embedding = %s::vector WHERE arcid = %s",
                    [(d, s, v, a) for (a, d, s, v) in pending],
                )
            conn.commit()

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
