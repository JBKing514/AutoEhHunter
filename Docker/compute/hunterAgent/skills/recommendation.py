import math
import json
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence

from hunterAgent.core.ai import ChatMessage, OpenAICompatClient
from hunterAgent.core.config import Settings
from hunterAgent.core.db import (
    get_eh_candidates_by_period,
    get_profile_samples_from_inventory,
    get_profile_samples_from_reads,
)


@dataclass
class _RecProfileCache:
    built_at: float
    days: int
    source: str
    tag_scores: Dict[str, float]
    centroids: List[List[float]]
    sample_count: int


_profile_cache: Optional[_RecProfileCache] = None


def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, float(v)))


def _as_bool(v: Any) -> bool:
    if isinstance(v, bool):
        return v
    s = str(v or "").strip().lower()
    return s in ("1", "true", "yes", "y", "on")


def _l2(a: Sequence[float], b: Sequence[float]) -> float:
    n = min(len(a), len(b))
    if n == 0:
        return 1e9
    s = 0.0
    for i in range(n):
        d = float(a[i]) - float(b[i])
        s += d * d
    return math.sqrt(s)


def _avg_vec(vs: Sequence[Sequence[float]]) -> List[float]:
    if not vs:
        return []
    dim = len(vs[0])
    acc = [0.0] * dim
    for v in vs:
        if len(v) != dim:
            continue
        for i in range(dim):
            acc[i] += float(v[i])
    m = float(len(vs))
    if m <= 0:
        return []
    return [x / m for x in acc]


def _kmeans(points: List[List[float]], k: int, iters: int = 8) -> List[List[float]]:
    if not points:
        return []
    pts = [p for p in points if p]
    if not pts:
        return []
    k = max(1, min(int(k), len(pts)))

    # Deterministic init by quantile picks.
    seeds: List[List[float]] = []
    n = len(pts)
    for i in range(k):
        idx = int((i + 0.5) * n / k)
        if idx >= n:
            idx = n - 1
        seeds.append(list(pts[idx]))
    centroids = seeds

    for _ in range(max(1, int(iters))):
        buckets: List[List[List[float]]] = [[] for _ in range(k)]
        for p in pts:
            best_i = 0
            best_d = float("inf")
            for i, c in enumerate(centroids):
                d = _l2(p, c)
                if d < best_d:
                    best_d = d
                    best_i = i
            buckets[best_i].append(p)

        new_centroids: List[List[float]] = []
        for i in range(k):
            if buckets[i]:
                new_centroids.append(_avg_vec(buckets[i]))
            else:
                new_centroids.append(centroids[i])
        centroids = new_centroids

    return centroids


def _build_tag_scores(samples: List[Dict[str, Any]]) -> Dict[str, float]:
    counts: Dict[str, int] = {}
    for s in samples:
        for t in (s.get("tags") or []):
            tag = str(t or "").strip()
            if not tag:
                continue
            counts[tag] = counts.get(tag, 0) + 1
    if not counts:
        return {}
    max_freq = max(counts.values())
    if max_freq <= 0:
        return {}
    out: Dict[str, float] = {}
    for tag, freq in counts.items():
        # Smooth score: 0..1
        out[tag] = math.log1p(float(freq)) / math.log1p(float(max_freq))
    return out


def _build_profile(settings: Settings, profile_days: int) -> _RecProfileCache:
    now = int(time.time())
    start = now - int(profile_days) * 24 * 3600

    samples = get_profile_samples_from_reads(settings, start, now, limit=800)
    source = "reads"
    if len(samples) < 20:
        # Fallback: recent library additions (last 30 days), not reading history.
        inv_start = now - 30 * 24 * 3600
        samples = get_profile_samples_from_inventory(settings, inv_start, now, limit=800)
        source = "inventory_date_added_30d"

    tag_scores = _build_tag_scores(samples)
    points: List[List[float]] = []
    for s in samples:
        vec = s.get("visual_embedding") or []
        if isinstance(vec, list) and len(vec) > 0:
            points.append([float(x) for x in vec])

    # Bound clustering cost.
    if len(points) > 320:
        step = max(1, len(points) // 320)
        points = points[::step]

    centroids = _kmeans(points, k=max(1, int(settings.rec_cluster_k)), iters=8)
    return _RecProfileCache(
        built_at=time.time(),
        days=int(profile_days),
        source=source,
        tag_scores=tag_scores,
        centroids=centroids,
        sample_count=len(samples),
    )


def _get_profile_cached(settings: Settings, profile_days: int) -> _RecProfileCache:
    global _profile_cache
    now = time.time()
    ttl = max(60, int(settings.rec_cluster_cache_ttl_s))
    if _profile_cache is not None:
        if _profile_cache.days == int(profile_days) and now - _profile_cache.built_at <= ttl:
            return _profile_cache
    _profile_cache = _build_profile(settings, profile_days)
    return _profile_cache


def _tag_component(tags: Sequence[str], tag_scores: Dict[str, float], floor: float) -> float:
    arr = [str(t or "").strip() for t in tags if str(t or "").strip()]
    if not arr:
        return float(floor)
    vals = [float(tag_scores.get(t, floor)) for t in arr]
    return float(sum(vals) / len(vals))


def _build_recommend_narrative(
    *,
    llm: OpenAICompatClient,
    settings: Settings,
    profile_source: str,
    profile_days: int,
    candidate_hours: int,
    results: Sequence[Dict[str, Any]],
) -> str:
    if not results:
        return "当前时间窗口内没有合适的库外候选，建议放宽时间范围后再试。"

    sample = [
        {
            "rank": r.get("rank"),
            "title": r.get("title"),
            "tags": (r.get("tags") or [])[:6],
            "tags_translated": (r.get("tags_translated") or [])[:6],
        }
        for r in list(results)[:8]
    ]
    system = (
        "你是代号 'Alice' 的战术资料库副官。你刚刚从外部网络（E-Hentai）的最新上传流中，为指挥官筛选了一批潜在的高价值补给。\n"
        "你的任务：\n"
        "1. **邀功请赏**：强调这些是你根据他的'历史作战偏好'（XP 聚类）特意挑选的。\n"
        "2. **推荐理由**：指出这批新货命中了什么好球区（例如：'这批新货完美契合您对黑长直的执念'）。\n"
        "3. **试探性建议**：如果开启了探索模式，可以说'顺便夹带了一点私货，也许您会打开新世界的大门'。\n"
    )
    user = (
        f"profile_source={profile_source}, profile_days={profile_days}, candidate_hours={candidate_hours}\n"
        f"sample={json.dumps(sample, ensure_ascii=False)}"
    )
    try:
        txt = llm.chat(
            model=settings.llm_model,
            messages=[ChatMessage(role="system", content=system), ChatMessage(role="user", content=user)],
            temperature=0.4,
            max_tokens=260,
        )
        t = str(txt or "").strip()
        if t:
            return t
    except Exception:
        pass
    return "已按你的偏好筛选库外候选，前排结果更贴近近期口味。"


def _extract_source_urls(tags: Sequence[str]) -> tuple[str, str]:
    eh_url = ""
    ex_url = ""
    for tag in tags or []:
        s = str(tag or "").strip()
        if not s.lower().startswith("source:"):
            continue
        v = s.split(":", 1)[1].strip()
        if not v:
            continue
        if not v.startswith("http://") and not v.startswith("https://"):
            v = f"https://{v}"
        if "exhentai.org" in v:
            ex_url = ex_url or v
        elif "e-hentai.org" in v:
            eh_url = eh_url or v
    return eh_url, ex_url


def run_recommendation(*, settings: Settings, llm: OpenAICompatClient, payload: Dict[str, Any]) -> Dict[str, Any]:
    now = int(time.time())
    k = max(1, min(50, int(payload.get("k") or 10)))

    profile_days = max(1, min(365, int(payload.get("profile_days") or settings.rec_profile_days)))
    candidate_hours = max(1, min(24 * 30, int(payload.get("candidate_hours") or settings.rec_candidate_hours)))
    candidate_limit = max(50, min(2000, int(payload.get("candidate_limit") or settings.rec_candidate_limit)))

    tag_weight = float(payload.get("tag_weight") or settings.rec_tag_weight)
    visual_weight = float(payload.get("visual_weight") or settings.rec_visual_weight)
    if tag_weight < 0:
        tag_weight = 0.0
    if visual_weight < 0:
        visual_weight = 0.0
    wsum = tag_weight + visual_weight
    if wsum <= 0:
        tag_weight = 0.55
        visual_weight = 0.45
        wsum = 1.0
    tag_weight /= wsum
    visual_weight /= wsum

    strictness = _clamp(float(payload.get("strictness") or settings.rec_strictness), 0.0, 1.0)
    mode = str(payload.get("mode") or "").strip().lower()
    explore = _as_bool(payload.get("explore")) or mode == "explore"
    precise = _as_bool(payload.get("precise")) or mode == "precise"
    if explore:
        strictness = _clamp(strictness - 0.20, 0.0, 1.0)
    if precise:
        strictness = _clamp(strictness + 0.20, 0.0, 1.0)

    profile = _get_profile_cached(settings, profile_days)
    start = now - candidate_hours * 3600
    candidates = get_eh_candidates_by_period(settings, start, now, limit=candidate_limit)

    floor = _clamp(float(payload.get("tag_floor_score") or settings.rec_tag_floor_score), 0.0, 0.4)
    min_tag = 0.04 + 0.36 * strictness
    min_visual = 0.15 + 0.55 * strictness

    scored: List[Dict[str, Any]] = []
    for c in candidates:
        tags = c.get("tags") or []
        tscore = _tag_component(tags, profile.tag_scores, floor)

        vscore = 0.45
        min_dist = None
        vec = c.get("cover_embedding") or []
        if profile.centroids and isinstance(vec, list) and vec:
            dists = [_l2(vec, center) for center in profile.centroids]
            if dists:
                min_dist = min(dists)
                vscore = 1.0 / (1.0 + float(min_dist))

        if (not explore) and tscore < min_tag and vscore < min_visual:
            continue

        novelty_bonus = (1.0 - tscore) * 0.12 if explore else 0.0
        precision_bonus = ((tscore + vscore) * 0.5) * (0.08 * strictness)
        final = tag_weight * tscore + visual_weight * vscore + novelty_bonus + precision_bonus

        scored.append(
            {
                "gid": c.get("gid"),
                "token": c.get("token"),
                "title": c.get("title") or "",
                "title_jpn": c.get("title_jpn") or "",
                "eh_url": c.get("eh_url"),
                "ex_url": c.get("ex_url"),
                "posted": c.get("posted"),
                "tags": c.get("tags") or [],
                "tags_translated": c.get("tags_translated") or [],
                "score": float(final),
                "signals": {
                    "tag_score": float(tscore),
                    "visual_score": float(vscore),
                    "min_cluster_distance": min_dist,
                },
            }
        )

    scored.sort(key=lambda x: float(x.get("score") or 0.0), reverse=True)
    top = scored[:k]

    results: List[Dict[str, Any]] = []
    for i, item in enumerate(top, start=1):
        tags = item.get("tags") or []
        src_eh, src_ex = _extract_source_urls(tags)
        eh_url = item.get("eh_url") or src_eh or ""
        ex_url = item.get("ex_url") or src_ex or ""
        results.append(
            {
                "source": "eh_works",
                "title": item.get("title") or item.get("title_jpn") or "",
                "rank": i,
                "reader_url": "",
                "eh_url": eh_url,
                "ex_url": ex_url,
                "tags": tags,
                "tags_translated": item.get("tags_translated") or [],
            }
        )

    narrative = _build_recommend_narrative(
        llm=llm,
        settings=settings,
        profile_source=profile.source,
        profile_days=profile_days,
        candidate_hours=candidate_hours,
        results=results,
    )

    return {
        "intent": "RECOMMEND",
        "narrative": narrative,
        "results": results,
    }
