import json
import hashlib
import math
import random
import re
import threading
import time
from datetime import datetime, timezone
from typing import Any

from plotly import figure_factory as ff
from plotly.utils import PlotlyJSONEncoder
from scipy.cluster import hierarchy as sch
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA
from sklearn.feature_extraction.text import TfidfVectorizer

from .db_service import query_rows
from .recommend_feedback_service import get_action_counts, get_interaction_revision, recommendation_key
from .recommend_profile_service import get_user_profile_vector
from .search_service import _item_from_eh

_SOURCE_GALLERY_RE = re.compile(r"source:\s*https?://(?:e-hentai|exhentai)\.org/g/(\d+)/([a-z0-9]+)/")


def _normalize_tags(raw: Any) -> list[str]:
    if isinstance(raw, list):
        return [str(x).strip() for x in raw if str(x).strip()]
    if isinstance(raw, tuple):
        return [str(x).strip() for x in list(raw) if str(x).strip()]
    if raw is None:
        return []
    s = str(raw).strip()
    if not s:
        return []
    return [s]


def _date_to_epoch(date_txt: str, end_of_day: bool = False) -> int | None:
    s = str(date_txt or "").strip()
    if not s:
        return None
    try:
        d = datetime.strptime(s, "%Y-%m-%d")
        if end_of_day:
            dt = datetime(d.year, d.month, d.day, 23, 59, 59, tzinfo=timezone.utc)
        else:
            dt = datetime(d.year, d.month, d.day, 0, 0, 0, tzinfo=timezone.utc)
        return int(dt.timestamp())
    except Exception:
        return None


def _compute_xp_map(
    mode: str,
    time_basis: str,
    max_points: int,
    days: int,
    k: int,
    topn: int,
    exclude_language_tags: bool,
    exclude_other_tags: bool,
    start_date: str = "",
    end_date: str = "",
    exclude_tags: list[str] | None = None,
    dendro_page: int = 1,
    dendro_page_size: int = 100,
) -> dict[str, Any]:
    horizon_s = int(days * 86400)
    now_ep = int(datetime.now(timezone.utc).timestamp())
    start_ep = _date_to_epoch(start_date, end_of_day=False)
    end_ep = _date_to_epoch(end_date, end_of_day=True)
    if start_ep is None:
        start_ep = now_ep - horizon_s
    if end_ep is None:
        end_ep = now_ep
    if end_ep < start_ep:
        end_ep = start_ep
    exclude_tags_set = {str(x).strip().lower() for x in (exclude_tags or []) if str(x).strip()}
    if mode == "read_history":
        sql = (
            "SELECT DISTINCT w.arcid, w.title, w.tags FROM works w JOIN read_events r ON r.arcid = w.arcid "
            "WHERE r.read_time >= %s AND r.read_time <= %s LIMIT %s"
        )
        rows = query_rows(sql, (int(start_ep), int(end_ep), int(max_points)))
    else:
        basis_col = "eh_posted" if time_basis == "eh_posted" else "date_added"
        sql = (
            f"SELECT w.arcid, w.title, w.tags FROM works w "
            f"WHERE coalesce(w.{basis_col}, 0) >= %s AND coalesce(w.{basis_col}, 0) <= %s LIMIT %s"
        )
        rows = query_rows(sql, (int(start_ep), int(end_ep), int(max_points)))

    if not rows:
        return {"points": [], "clusters": [], "meta": {"reason": "no_data"}}

    lang_prefixes = ("language:", "语言:")
    other_prefixes = ("other:", "misc:", "其他:", "杂项:")
    hard_block_prefixes = ("uploader:", "date_added:", "上传者:", "入库时间:")

    def _keep_tag(tag: str) -> bool:
        low = str(tag).strip().lower()
        if low.startswith(hard_block_prefixes):
            return False
        if exclude_language_tags and low.startswith(lang_prefixes):
            return False
        if exclude_other_tags and low.startswith(other_prefixes):
            return False
        if low in exclude_tags_set:
            return False
        return True

    docs = [" ".join([tg for tg in _normalize_tags(r.get("tags")) if _keep_tag(tg)]) for r in rows]
    if len(docs) < 4 or sum(len(d.strip()) > 0 for d in docs) < 4:
        return {"points": [], "clusters": [], "meta": {"reason": "no_tags"}}

    vec = TfidfVectorizer(max_features=3000, token_pattern=r"[^\s]+")
    X = vec.fit_transform(docs)
    feature_names = vec.get_feature_names_out().tolist()
    n_samples = X.shape[0]
    k_use = min(k, max(2, n_samples // 2))
    km = KMeans(n_clusters=k_use, n_init=10, random_state=42)
    labels = km.fit_predict(X)

    centers = km.cluster_centers_
    cluster_name_map: dict[int, str] = {}
    cluster_top_terms: dict[int, list[str]] = {}
    for cid in range(k_use):
        weights = centers[cid].tolist() if hasattr(centers[cid], "tolist") else list(centers[cid])
        ranked_idx = sorted(range(len(weights)), key=lambda i: weights[i], reverse=True)[:topn]
        top_terms = [feature_names[i] for i in ranked_idx if i < len(feature_names) and weights[i] > 0]
        cluster_top_terms[cid] = top_terms
        cluster_name_map[cid] = " / ".join(top_terms) if top_terms else f"cluster-{cid}"

    pca = PCA(n_components=2, random_state=42)
    coords = pca.fit_transform(X.toarray())

    def _wrap_terms(terms: list[str], line_size: int = 3) -> str:
        if not terms:
            return "-"
        chunks = [terms[i : i + line_size] for i in range(0, len(terms), line_size)]
        return "<br>".join([", ".join(c) for c in chunks])

    def _axis_semantics(comp_idx: int) -> str:
        if comp_idx >= len(pca.components_):
            return "insufficient signal"
        comp = pca.components_[comp_idx]
        ranked_pos = sorted(range(len(comp)), key=lambda i: float(comp[i]), reverse=True)[: min(6, topn * 2)]
        ranked_neg = sorted(range(len(comp)), key=lambda i: float(comp[i]))[: min(6, topn * 2)]
        pos_terms = [feature_names[i] for i in ranked_pos if i < len(feature_names) and float(comp[i]) > 0]
        neg_terms = [feature_names[i] for i in ranked_neg if i < len(feature_names) and float(comp[i]) < 0]
        if not pos_terms and not neg_terms:
            return "insufficient signal"
        return f"+: {_wrap_terms(pos_terms)}<br>-: {_wrap_terms(neg_terms)}"

    x_var = float(pca.explained_variance_ratio_[0]) if len(pca.explained_variance_ratio_) > 0 else 0.0
    y_var = float(pca.explained_variance_ratio_[1]) if len(pca.explained_variance_ratio_) > 1 else 0.0
    x_title = f"PC1 ({round(x_var * 100.0, 1)}% variance) {_axis_semantics(0)}"
    y_title = f"PC2 ({round(y_var * 100.0, 1)}% variance) {_axis_semantics(1)}"

    points: list[dict[str, Any]] = []
    for idx, row in enumerate(rows):
        cid = int(labels[idx])
        points.append(
            {
                "x": float(coords[idx, 0]),
                "y": float(coords[idx, 1]),
                "cluster_id": cid,
                "cluster": cluster_name_map.get(cid, f"cluster-{cid}"),
                "title": str(row.get("title") or ""),
                "arcid": str(row.get("arcid") or ""),
            }
        )

    clusters = []
    for cid in range(k_use):
        clusters.append(
            {
                "cluster_id": cid,
                "name": cluster_name_map.get(cid, f"cluster-{cid}"),
                "top_terms": cluster_top_terms.get(cid, []),
                "count": int(sum(1 for x in labels if int(x) == cid)),
            }
        )

    dendrogram = {"available": False, "reason": "need_at_least_4_samples", "figure": None}
    try:
        if X.shape[0] >= 4:
            total = X.shape[0]
            page_size = max(20, min(300, int(dendro_page_size)))
            page = max(1, int(dendro_page))
            start = (page - 1) * page_size
            end = min(total, start + page_size)
            dendro_idx = list(range(total))[start:end]
            dense_subset = X[dendro_idx].toarray()
            label_subset: list[str] = []
            for i in dendro_idx:
                title = str(rows[i].get("title") or "").strip()
                label_subset.append((title[:30] + "..") if len(title) > 30 else title)

            linkage_matrix = sch.linkage(dense_subset, method="ward")
            fig = ff.create_dendrogram(
                dense_subset,
                labels=label_subset,
                orientation="left",
                linkagefun=lambda _: linkage_matrix,
            )
            fig.update_layout(
                width=1100,
                height=max(800, len(dendro_idx) * 25),
                margin={"l": 200, "r": 60, "t": 40, "b": 40},
                xaxis_title="Distance",
                yaxis_title="Library Samples",
                showlegend=False,
                hovermode=False,
            )
            dendrogram = {
                "available": True,
                "reason": "",
                "figure": json.loads(json.dumps(fig, cls=PlotlyJSONEncoder)),
                "sample_count": len(dendro_idx),
                "total_count": int(total),
                "page": page,
                "page_size": page_size,
                "pages": max(1, (int(total) + page_size - 1) // page_size),
            }
    except Exception as e:
        dendrogram = {"available": False, "reason": f"dendrogram_error: {e}", "figure": None}

    return {
        "points": points,
        "clusters": clusters,
        "dendrogram": dendrogram,
        "meta": {
            "n_points": len(points),
            "k": k_use,
            "x_variance_ratio": x_var,
            "y_variance_ratio": y_var,
            "x_axis_title": x_title,
            "y_axis_title": y_title,
            "start_epoch": int(start_ep),
            "end_epoch": int(end_ep),
        },
    }


def _parse_vector_text(text: str) -> list[float]:
    s = str(text or "").strip()
    if not s:
        return []
    if s.startswith("[") and s.endswith("]"):
        s = s[1:-1]
    out: list[float] = []
    for part in [x.strip() for x in s.split(",") if x.strip()]:
        try:
            out.append(float(part))
        except Exception:
            continue
    return out


def _l2(a: list[float], b: list[float]) -> float:
    n = min(len(a), len(b))
    if n <= 0:
        return 1e9
    s = 0.0
    for i in range(n):
        d = float(a[i]) - float(b[i])
        s += d * d
    return math.sqrt(s)


def _cosine(a: list[float], b: list[float]) -> float:
    n = min(len(a), len(b))
    if n <= 0:
        return 0.0
    dot = 0.0
    na = 0.0
    nb = 0.0
    for i in range(n):
        av = float(a[i])
        bv = float(b[i])
        dot += av * bv
        na += av * av
        nb += bv * bv
    if na <= 0 or nb <= 0:
        return 0.0
    return float(dot / math.sqrt(na * nb))


def _project_1024(vec: list[float]) -> list[float]:
    if len(vec) >= 1024:
        return vec[:1024]
    if not vec:
        return []
    return vec + [0.0] * (1024 - len(vec))


def _normalize_l2(vec: list[float]) -> list[float]:
    if not vec:
        return []
    s = 0.0
    for x in vec:
        s += float(x) * float(x)
    if s <= 0:
        return vec
    inv = 1.0 / math.sqrt(s)
    return [float(x) * inv for x in vec]


def _jitter_rng(user_id: str, nonce: str) -> random.Random:
    seed_src = f"{str(user_id or 'default_user')}|{str(nonce or '')}|aeh-jitter-v1"
    seed_hex = hashlib.sha256(seed_src.encode("utf-8")).hexdigest()[:16]
    return random.Random(int(seed_hex, 16))


def _with_gaussian_jitter(vec: list[float], sigma: float, rng: random.Random) -> list[float]:
    if not vec:
        return []
    sig = max(0.0, min(0.25, float(sigma)))
    if sig <= 0:
        return vec
    out = [float(x) + float(rng.gauss(0.0, sig)) for x in vec]
    return _normalize_l2(out)


def _rec_profile_and_scores(cfg: dict[str, Any]) -> tuple[dict[str, float], list[list[float]], str, int]:
    profile_days = max(1, min(365, int(cfg.get("REC_PROFILE_DAYS", 30))))
    now_ep = int(time.time())
    start_ep = now_ep - profile_days * 86400
    samples = query_rows(
        "SELECT e.arcid, e.read_time, w.tags, w.visual_embedding::text as visual_vec "
        "FROM read_events e JOIN works w ON w.arcid = e.arcid "
        "WHERE e.read_time >= %s AND e.read_time < %s ORDER BY e.read_time DESC LIMIT 800",
        (int(start_ep), int(now_ep)),
    )
    source = "reads"
    if len(samples) < 20:
        inv_start = now_ep - 30 * 86400
        samples = query_rows(
            "SELECT arcid, tags, visual_embedding::text as visual_vec "
            "FROM works WHERE date_added IS NOT NULL "
            "AND (CASE WHEN date_added >= 100000000000 THEN date_added / 1000 ELSE date_added END) >= %s "
            "AND (CASE WHEN date_added >= 100000000000 THEN date_added / 1000 ELSE date_added END) < %s "
            "ORDER BY (CASE WHEN date_added >= 100000000000 THEN date_added / 1000 ELSE date_added END) DESC LIMIT 800",
            (int(inv_start), int(now_ep)),
        )
        source = "inventory_date_added_30d"

    counts: dict[str, int] = {}
    points: list[list[float]] = []
    for s in samples:
        for t in (s.get("tags") or []):
            tag = str(t or "").strip()
            if tag:
                counts[tag] = counts.get(tag, 0) + 1
        vec = _parse_vector_text(str(s.get("visual_vec") or ""))
        if vec:
            points.append(vec)

    max_freq = max(counts.values()) if counts else 0
    tag_scores: dict[str, float] = {}
    if max_freq > 0:
        for tag, freq in counts.items():
            tag_scores[tag] = math.log1p(float(freq)) / math.log1p(float(max_freq))

    if len(points) > 320:
        step = max(1, len(points) // 320)
        points = points[::step]
    k_clusters = max(1, min(8, int(cfg.get("REC_CLUSTER_K", 3))))
    if points and len(points) >= k_clusters:
        km = KMeans(n_clusters=k_clusters, n_init=10, random_state=42)
        km.fit(points)
        centroids = km.cluster_centers_.tolist()
    else:
        centroids = []
    return tag_scores, centroids, source, len(samples)


def _library_existing_keys(candidate_keys: set[str]) -> set[str]:
    keys = [str(x or "").strip().lower() for x in (candidate_keys or set()) if str(x or "").strip()]
    if not keys:
        return set()
    rows = query_rows(
        "SELECT DISTINCT ((parts)[1] || ':' || (parts)[2]) AS k "
        "FROM works w "
        "CROSS JOIN LATERAL unnest(w.tags) AS t(tag) "
        "CROSS JOIN LATERAL regexp_match(lower(t.tag), %s) AS m(parts) "
        "WHERE ((parts)[1] || ':' || (parts)[2]) = ANY(%s)",
        (_SOURCE_GALLERY_RE.pattern, keys),
    )
    return {str(r.get("k") or "").strip().lower() for r in rows if str(r.get("k") or "").strip()}


def _build_recommendation_items(
    cfg: dict[str, Any],
    mode: str = "",
    user_id: str = "default_user",
    depth: int = 1,
    jitter: bool = False,
    jitter_nonce: str = "",
) -> dict[str, Any]:
    strictness = float(cfg.get("REC_STRICTNESS", 0.55))
    strictness = max(0.0, min(1.0, strictness))
    mode_s = str(mode or "").strip().lower()
    explore = mode_s == "explore"
    precise = mode_s == "precise"
    if explore:
        strictness = max(0.0, min(1.0, strictness - 0.20))
    if precise:
        strictness = max(0.0, min(1.0, strictness + 0.20))

    rec_hours_base = max(1, min(24 * 30, int(cfg.get("REC_CANDIDATE_HOURS", 24))))
    rec_limit_base = max(50, min(2000, int(cfg.get("REC_CANDIDATE_LIMIT", 400))))
    depth_use = max(1, min(8, int(depth or 1)))
    dynamic_expand = str(cfg.get("REC_DYNAMIC_EXPAND_ENABLED", True)).strip().lower() in {"1", "true", "yes", "on"}
    factor = 1 if not dynamic_expand else (2 ** (depth_use - 1))
    rec_hours = max(1, min(24 * 30, int(rec_hours_base * factor)))
    rec_limit = max(50, min(2000, int(rec_limit_base * factor)))
    tag_weight = max(0.0, float(cfg.get("REC_TAG_WEIGHT", 0.55)))
    visual_weight = max(0.0, float(cfg.get("REC_VISUAL_WEIGHT", 0.45)))
    total_w = tag_weight + visual_weight
    if total_w <= 0:
        tag_weight, visual_weight, total_w = 0.55, 0.45, 1.0
    tag_weight = tag_weight / total_w
    visual_weight = visual_weight / total_w
    floor = max(0.0, min(0.4, float(cfg.get("REC_TAG_FLOOR_SCORE", 0.08))))
    touch_penalty_pct = max(0.0, min(100.0, float(cfg.get("REC_TOUCH_PENALTY_PCT", 35))))
    touch_penalty = touch_penalty_pct / 100.0
    impression_penalty_pct = max(0.0, min(100.0, float(cfg.get("REC_IMPRESSION_PENALTY_PCT", 3))))
    impression_penalty = impression_penalty_pct / 100.0

    tag_scores, centroids, profile_source, sample_count = _rec_profile_and_scores(cfg)
    now_ep = int(time.time())
    start_ep = now_ep - rec_hours * 3600
    candidates = query_rows(
        "SELECT gid, token, eh_url, ex_url, title, title_jpn, category, tags, tags_translated, posted, "
        "cover_embedding::text as cover_vec "
        "FROM eh_works WHERE posted IS NOT NULL AND posted >= %s AND posted < %s "
        "ORDER BY posted DESC LIMIT %s",
        (int(start_ep), int(now_ep), int(rec_limit)),
    )

    candidate_key_map: dict[str, str] = {}
    for c in candidates:
        gid = int(c.get("gid") or 0)
        token = str(c.get("token") or "").strip().lower()
        if not gid or not token:
            continue
        candidate_key_map[f"{gid}:{token}"] = recommendation_key(gid, token)

    in_library = _library_existing_keys(set(candidate_key_map.keys()))
    touch_counts = get_action_counts(str(user_id or "default_user"), list(candidate_key_map.values()), "click")
    impression_counts = get_action_counts(str(user_id or "default_user"), list(candidate_key_map.values()), "impression")
    dislike_counts = get_action_counts(str(user_id or "default_user"), list(candidate_key_map.values()), "dislike")
    read_counts = get_action_counts(str(user_id or "default_user"), list(candidate_key_map.values()), "read")
    profile_vec = get_user_profile_vector(str(user_id or "default_user"))
    profile_weight = 0.18
    jitter_sigma = 0.035
    jitter_enabled = bool(jitter)
    jitter_rng = _jitter_rng(str(user_id or "default_user"), str(jitter_nonce or "")) if jitter_enabled else None
    if jitter_enabled and len(profile_vec) == 1024 and jitter_rng is not None:
        profile_vec = _with_gaussian_jitter(profile_vec, jitter_sigma, jitter_rng)

    min_tag = 0.04 + 0.36 * strictness
    min_visual = 0.15 + 0.55 * strictness
    scored: list[dict[str, Any]] = []
    skipped_in_library = 0
    skipped_touch = 0
    skipped_dislike = 0
    skipped_read = 0
    for c in candidates:
        gid = int(c.get("gid") or 0)
        token = str(c.get("token") or "").strip().lower()
        if gid and token and f"{gid}:{token}" in in_library:
            skipped_in_library += 1
            continue

        tags = [str(x) for x in (c.get("tags") or []) if str(x).strip()]
        tscore = float(sum(float(tag_scores.get(t, floor)) for t in tags) / len(tags)) if tags else float(floor)
        vscore = 0.45
        min_dist = None
        vec = _parse_vector_text(str(c.get("cover_vec") or ""))
        if centroids and vec:
            dists = [_l2(vec, center) for center in centroids]
            if dists:
                min_dist = min(dists)
                vscore = 1.0 / (1.0 + float(min_dist))
        if (not explore) and tscore < min_tag and vscore < min_visual:
            continue
        novelty_bonus = (1.0 - tscore) * 0.12 if explore else 0.0
        precision_bonus = ((tscore + vscore) * 0.5) * (0.08 * strictness)
        final = tag_weight * tscore + visual_weight * vscore + novelty_bonus + precision_bonus

        rec_key = recommendation_key(gid, token)
        touch_n = int(touch_counts.get(rec_key, 0)) if rec_key else 0
        impression_n = int(impression_counts.get(rec_key, 0)) if rec_key else 0
        dislike_n = int(dislike_counts.get(rec_key, 0)) if rec_key else 0
        read_n = int(read_counts.get(rec_key, 0)) if rec_key else 0
        if dislike_n > 0:
            skipped_dislike += 1
            continue
        if read_n > 0:
            skipped_read += 1
            continue
        touch_factor = 1.0
        impression_factor = 1.0
        if touch_n > 0 and touch_penalty > 0:
            touch_factor = max(0.0, (1.0 - touch_penalty) ** touch_n)
            if touch_factor <= 0:
                skipped_touch += 1
                continue
        if impression_n > 0 and impression_penalty > 0:
            impression_factor = max(0.0, (1.0 - impression_penalty) ** impression_n)
        profile_score = 0.0
        if len(profile_vec) == 1024 and vec:
            sim = _cosine(profile_vec, _project_1024(vec))
            profile_score = max(0.0, min(1.0, (float(sim) + 1.0) * 0.5))
        final = float(final) * float(touch_factor) * float(impression_factor)
        final = final + profile_weight * profile_score
        if jitter_enabled and jitter_rng is not None:
            final = final + float(jitter_rng.gauss(0.0, 0.022))

        scored.append(
            {
                **c,
                "score": float(final),
                "signals": {
                    "tag_score": float(tscore),
                    "visual_score": float(vscore),
                    "min_cluster_distance": min_dist,
                    "touch_count": touch_n,
                    "touch_factor": float(touch_factor),
                    "impression_count": impression_n,
                    "impression_factor": float(impression_factor),
                    "profile_score": float(profile_score),
                    "dislike_count": dislike_n,
                    "read_count": read_n,
                },
            }
        )
    scored.sort(key=lambda x: float(x.get("score") or 0.0), reverse=True)
    return {
        "items": [_item_from_eh(x, cfg) | {"signals": x.get("signals") or {}} for x in scored],
        "meta": {
            "profile_source": profile_source,
            "profile_sample_count": int(sample_count),
            "candidate_hours": rec_hours,
            "candidate_hours_base": rec_hours_base,
            "candidate_limit": rec_limit,
            "candidate_limit_base": rec_limit_base,
            "strictness": strictness,
            "mode": mode_s or "default",
            "depth": depth_use,
            "dynamic_expand_enabled": dynamic_expand,
            "can_expand_more": bool(dynamic_expand and (rec_hours < 24 * 30 or rec_limit < 2000)),
            "jitter": jitter_enabled,
            "jitter_nonce": str(jitter_nonce or ""),
            "touch_penalty_pct": touch_penalty_pct,
            "impression_penalty_pct": impression_penalty_pct,
            "excluded_in_library": skipped_in_library,
            "excluded_by_touch": skipped_touch,
            "excluded_by_dislike": skipped_dislike,
            "excluded_by_read": skipped_read,
        },
    }


_home_rec_cache_lock = threading.Lock()
_home_rec_cache: dict[str, Any] = {"built_at": 0.0, "key": "", "items": []}


def _get_recommendation_items_cached(
    cfg: dict[str, Any],
    mode: str = "",
    user_id: str = "default_user",
    depth: int = 1,
    jitter: bool = False,
    jitter_nonce: str = "",
) -> dict[str, Any]:
    ttl = max(60, int(cfg.get("REC_CLUSTER_CACHE_TTL_S", 900)))
    mode_s = str(mode or "").strip().lower()
    touch_rev = get_interaction_revision(str(user_id or "default_user"))
    key = "|".join(
        [
            str(user_id or "default_user"),
            touch_rev,
            str(max(1, min(8, int(depth or 1)))),
            mode_s,
            str(cfg.get("REC_PROFILE_DAYS")),
            str(cfg.get("REC_CANDIDATE_HOURS")),
            str(cfg.get("REC_CLUSTER_K")),
            str(cfg.get("REC_TAG_WEIGHT")),
            str(cfg.get("REC_VISUAL_WEIGHT")),
            str(cfg.get("REC_STRICTNESS")),
            str(cfg.get("REC_CANDIDATE_LIMIT")),
            str(cfg.get("REC_TAG_FLOOR_SCORE")),
            str(cfg.get("REC_TOUCH_PENALTY_PCT")),
            str(cfg.get("REC_IMPRESSION_PENALTY_PCT")),
            str(cfg.get("REC_DYNAMIC_EXPAND_ENABLED")),
            str(bool(jitter)),
            str(jitter_nonce or ""),
        ]
    )
    now_t = time.time()
    with _home_rec_cache_lock:
        if _home_rec_cache.get("key") == key and (now_t - float(_home_rec_cache.get("built_at") or 0.0) <= ttl):
            return {
                "items": list(_home_rec_cache.get("items") or []),
                "meta": dict(_home_rec_cache.get("meta") or {}),
            }
    built = _build_recommendation_items(
        cfg,
        mode=mode_s,
        user_id=str(user_id or "default_user"),
        depth=depth,
        jitter=bool(jitter),
        jitter_nonce=str(jitter_nonce or ""),
    )
    with _home_rec_cache_lock:
        _home_rec_cache["built_at"] = now_t
        _home_rec_cache["key"] = key
        _home_rec_cache["items"] = list(built.get("items") or [])
        _home_rec_cache["meta"] = dict(built.get("meta") or {})
    return built


def _cached_home_recommend(
    cfg: dict[str, Any],
    mode: str = "",
    user_id: str = "default_user",
    depth: int = 1,
    jitter: bool = False,
    jitter_nonce: str = "",
) -> dict[str, Any]:
    return _get_recommendation_items_cached(
        cfg,
        mode=mode,
        user_id=user_id,
        depth=depth,
        jitter=jitter,
        jitter_nonce=jitter_nonce,
    )


def _profile_summary_text(*args, **kwargs) -> str:
    return ""


def _recommendation_chat_payload(*args, **kwargs) -> dict[str, Any]:
    return {}
