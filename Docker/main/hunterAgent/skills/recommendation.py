import math
import json
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence

import psycopg
from sklearn.cluster import KMeans, MiniBatchKMeans
from sklearn.metrics.pairwise import cosine_similarity

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


def _cosine_similarity(a: Sequence[float], b: Sequence[float]) -> float:
    if not a or not b:
        return 0.0
    dot = 0.0
    norm_a = 0.0
    norm_b = 0.0
    for i in range(min(len(a), len(b))):
        av = float(a[i])
        bv = float(b[i])
        dot += av * bv
        norm_a += av * av
        norm_b += bv * bv
    if norm_a <= 0 or norm_b <= 0:
        return 0.0
    return dot / (math.sqrt(norm_a) * math.sqrt(norm_b))


def _get_user_base_vector(settings: Settings, user_id: str) -> List[float]:
    dsn = str(settings.postgres_dsn or "").strip()
    if not dsn:
        return []
    uid = str(user_id or "default_user")
    try:
        with psycopg.connect(dsn) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT base_vector FROM user_profiles WHERE user_id = %s LIMIT 1",
                    (uid,)
                )
                row = cur.fetchone()
                if row and row[0]:
                    vec = row[0]
                    if isinstance(vec, list):
                        return [float(x) for x in vec]
    except Exception:
        pass
    return []

def _kmeans(points: List[List[float]], k: int) -> List[List[float]]:
    if not points:
        return []
    dim = len(points[0]) if points else 0
    pts = [p for p in points if p and len(p) == dim]
    if not pts:
        return []
    k = max(1, min(int(k), len(pts)))
    if len(pts) > 1000:
        model = MiniBatchKMeans(
            n_clusters=k,
            n_init=3,
            max_iter=300,
            random_state=42,
        )
    else:
        model = KMeans(
            n_clusters=k,
            n_init=3,
            max_iter=300,
            random_state=42,
            algorithm="lloyd",
        )
    model.fit(pts)
    return model.cluster_centers_.tolist()


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

    centroids = _kmeans(points, k=max(1, int(settings.rec_cluster_k)))
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
            max_tokens=1800,
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

    user_id = str(payload.get("user_id") or "default_user")

    profile_days = max(1, min(365, int(payload.get("profile_days") or settings.rec_profile_days)))
    candidate_hours = max(1, min(24 * 30, int(payload.get("candidate_hours") or settings.rec_candidate_hours)))
    candidate_limit = max(50, min(2000, int(payload.get("candidate_limit") or settings.rec_candidate_limit)))

    tag_weight = float(payload.get("tag_weight") or settings.rec_tag_weight)
    visual_weight = float(payload.get("visual_weight") or settings.rec_visual_weight)
    feedback_weight = float(payload.get("feedback_weight") or getattr(settings, "rec_feedback_weight", 0.0))
    if tag_weight < 0:
        tag_weight = 0.0
    if visual_weight < 0:
        visual_weight = 0.0
    if feedback_weight < 0:
        feedback_weight = 0.0
    wsum = tag_weight + visual_weight + feedback_weight
    if wsum <= 0:
        tag_weight = 0.55
        visual_weight = 0.45
        feedback_weight = 0.0
        wsum = 1.0
    tag_weight /= wsum
    visual_weight /= wsum
    feedback_weight /= wsum

    # --- MAP Boltzmann temperature mapping ---
    # REC_TEMPERATURE: user-configurable base T; mode offsets applied on top.
    T_base = _clamp(float(payload.get("temperature") or getattr(settings, "rec_temperature", 0.3)), 0.05, 2.0)
    mode = str(payload.get("mode") or "").strip().lower()
    explore = _as_bool(payload.get("explore")) or mode == "explore"
    precise = _as_bool(payload.get("precise")) or mode == "precise"
    if explore:
        T = min(2.0, T_base + 0.5)
    elif precise:
        T = max(0.05, T_base - 0.2)
    else:
        T = T_base

    # Energy cutoff derived from temperature (hotter → looser cutoff).
    U_max = max(0.4, min(1.0, 1.0 - 0.55 * (1.0 - T / 2.0)))

    profile = _get_profile_cached(settings, profile_days)
    base_vector = _get_user_base_vector(settings, user_id) if feedback_weight > 0 else []

    start = now - candidate_hours * 3600
    candidates = get_eh_candidates_by_period(settings, start, now, limit=candidate_limit)

    floor = _clamp(float(payload.get("tag_floor_score") or settings.rec_tag_floor_score), 0.0, 0.4)

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

        # --- MAP Potential energies (normalised to [0,1]) ---
        U_tag = 1.0 - tscore
        U_vis = 1.0 - vscore

        # --- U_profile: feedback vector as third potential field ---
        fscore = 0.0
        U_profile = 0.5  # neutral default
        if base_vector and isinstance(vec, list) and vec and feedback_weight > 0:
            fscore = _cosine_similarity(vec, base_vector)
            U_profile = 1.0 - max(0.0, min(1.0, (fscore + 1.0) * 0.5))

        # --- MAP additive potential (three independent fields) ---
        triple_w = tag_weight + visual_weight + feedback_weight
        if triple_w <= 0:
            triple_w = 1.0
        U_total = (tag_weight * U_tag + visual_weight * U_vis + feedback_weight * U_profile) / triple_w

        # Energy cutoff: too far from attractor → skip
        if U_total > U_max:
            continue

        # --- MAP Boltzmann base probability: one mapping, no external linear terms ---
        final = math.exp(-U_total / T)

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
                    "feedback_score": float(fscore),
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
