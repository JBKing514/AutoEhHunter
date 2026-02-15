import os
from dataclasses import dataclass


def _env_int(name: str, default: int) -> int:
    v = os.getenv(name)
    if v is None or not str(v).strip():
        return default
    try:
        return int(str(v).strip())
    except Exception:
        return default


def _env_float(name: str, default: float) -> float:
    v = os.getenv(name)
    if v is None or not str(v).strip():
        return default
    try:
        return float(str(v).strip())
    except Exception:
        return default


@dataclass(frozen=True)
class Settings:
    # Postgres
    postgres_dsn: str

    # OpenAI-compatible chat (LLM)
    llm_api_base: str
    llm_api_key: str
    llm_model: str

    # OpenAI-compatible embeddings
    emb_api_base: str
    emb_api_key: str
    emb_model: str

    # Tag cache / fuzzy match
    hot_tag_min_freq: int
    hot_tag_cache_ttl_s: int
    tag_fuzzy_threshold: int

    # Search defaults
    search_candidates_per_source: int
    search_rrf_k: int

    # SigLIP (optional)
    siglip_model: str
    siglip_device: str

    # Recommendation defaults
    rec_profile_days: int
    rec_candidate_hours: int
    rec_cluster_k: int
    rec_cluster_cache_ttl_s: int
    rec_tag_weight: float
    rec_visual_weight: float
    rec_strictness: float
    rec_candidate_limit: int
    rec_tag_floor_score: float


def get_settings() -> Settings:
    dsn = os.getenv("POSTGRES_DSN", "").strip()
    if not dsn:
        # Keep behavior explicit: fail early instead of guessing host/user/password.
        raise RuntimeError("Missing POSTGRES_DSN")

    return Settings(
        postgres_dsn=dsn,
        llm_api_base=os.getenv("LLM_API_BASE", os.getenv("OPENAI_API_BASE", "http://127.0.0.1:8000/v1")).strip(),
        llm_api_key=os.getenv("LLM_API_KEY", os.getenv("OPENAI_API_KEY", "")).strip(),
        llm_model=os.getenv("LLM_MODEL", os.getenv("OPENAI_MODEL", "qwen3-next-80b-3card")).strip() or "qwen3-next-80b-3card",
        emb_api_base=os.getenv("EMB_API_BASE", "http://127.0.0.1:8000/v1").strip(),
        emb_api_key=os.getenv("EMB_API_KEY", os.getenv("OPENAI_API_KEY", "")).strip(),
        emb_model=os.getenv("EMB_MODEL", "bge-m3").strip() or "bge-m3",
        hot_tag_min_freq=_env_int("HOT_TAG_MIN_FREQ", 5),
        hot_tag_cache_ttl_s=_env_int("HOT_TAG_CACHE_TTL_S", 6 * 3600),
        tag_fuzzy_threshold=_env_int("TAG_FUZZY_THRESHOLD", 90),
        search_candidates_per_source=_env_int("SEARCH_CANDIDATES_PER_SOURCE", 50),
        search_rrf_k=_env_int("SEARCH_RRF_K", 60),
        siglip_model=os.getenv("SIGLIP_MODEL", "google/siglip-so400m-patch14-384").strip(),
        siglip_device=os.getenv("SIGLIP_DEVICE", "cpu").strip() or "cpu",
        rec_profile_days=_env_int("REC_PROFILE_DAYS", 30),
        rec_candidate_hours=_env_int("REC_CANDIDATE_HOURS", 24),
        rec_cluster_k=_env_int("REC_CLUSTER_K", 3),
        rec_cluster_cache_ttl_s=_env_int("REC_CLUSTER_CACHE_TTL_S", 900),
        rec_tag_weight=_env_float("REC_TAG_WEIGHT", 0.55),
        rec_visual_weight=_env_float("REC_VISUAL_WEIGHT", 0.45),
        rec_strictness=_env_float("REC_STRICTNESS", 0.55),
        rec_candidate_limit=_env_int("REC_CANDIDATE_LIMIT", 400),
        rec_tag_floor_score=_env_float("REC_TAG_FLOOR_SCORE", 0.08),
    )
