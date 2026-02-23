import os
import base64
from dataclasses import dataclass
from pathlib import Path

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF


def _get_config_cipher_key() -> bytes | None:
    key_env = os.getenv("DATA_UI_CONFIG_CRYPT_KEY", "").strip()
    if key_env:
        if len(key_env) == 44 and key_env.endswith("="):
            return key_env.encode("ascii")
        hkdf = HKDF(
            algorithm=hashes.SHA256(),
            length=32,
            salt=b"AutoEhHunter.ConfigCipher.Salt.v1",
            info=b"AutoEhHunter.ConfigCipher.Fernet.v1",
        )
        return base64.urlsafe_b64encode(hkdf.derive(key_env.encode("utf-8")))

    key_candidates = [
        Path("/app/runtime/webui/.app_config.key"),
        Path("/app/runtime/.app_config.key"),
    ]
    for p in key_candidates:
        if p.exists():
            try:
                return p.read_bytes().strip()
            except Exception:
                continue
    return None


def _get_config_cipher_key_legacy() -> bytes | None:
    key_env = os.getenv("DATA_UI_CONFIG_CRYPT_KEY", "").strip()
    if not key_env or (len(key_env) == 44 and key_env.endswith("=")):
        return None
    try:
        return base64.urlsafe_b64encode(key_env.encode("utf-8")[:32].ljust(32, b"0"))
    except Exception:
        return None


def _decrypt_secret_if_needed(value: str) -> str:
    s = str(value or "").strip()
    if not s.startswith("enc:v1:"):
        return s
    key = _get_config_cipher_key()
    legacy_key = _get_config_cipher_key_legacy()
    if not key and not legacy_key:
        return ""
    try:
        from cryptography.fernet import Fernet

        token = s[len("enc:v1:") :]
        if key:
            try:
                return Fernet(key).decrypt(token.encode("utf-8")).decode("utf-8")
            except Exception:
                pass
        if legacy_key:
            return Fernet(legacy_key).decrypt(token.encode("utf-8")).decode("utf-8")
        return ""
    except Exception:
        return ""


def _load_runtime_config_from_db(dsn: str) -> dict[str, str]:
    s = str(dsn or "").strip()
    if not s:
        return {}
    try:
        import psycopg
    except Exception:
        return {}

    sql = "SELECT key, value, is_secret FROM app_config WHERE scope = %s"
    out: dict[str, str] = {}
    try:
        with psycopg.connect(s) as conn:
            with conn.cursor() as cur:
                cur.execute(sql, ("global",))
                for key, value, is_secret in cur.fetchall():
                    k = str(key)
                    v = str(value or "")
                    out[k] = _decrypt_secret_if_needed(v) if bool(is_secret) else v
    except Exception:
        return {}
    return out


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

    # Prompt templates from data app config
    prompt_search_narrative_system: str
    prompt_profile_system: str
    prompt_report_system: str
    prompt_tag_extract_system: str


def get_settings() -> Settings:
    dsn = os.getenv("POSTGRES_DSN", "").strip()
    if not dsn:
        # Keep behavior explicit: fail early instead of guessing host/user/password.
        raise RuntimeError("Missing POSTGRES_DSN")

    db_cfg = _load_runtime_config_from_db(dsn)

    def _cfg(name: str, default: str = "") -> str:
        v = db_cfg.get(name)
        if v is not None and str(v).strip():
            return str(v).strip()
        return os.getenv(name, default).strip()

    def _cfg_int(name: str, default: int) -> int:
        raw = _cfg(name, str(default))
        try:
            return int(raw)
        except Exception:
            return int(default)

    def _cfg_float(name: str, default: float) -> float:
        raw = _cfg(name, str(default))
        try:
            return float(raw)
        except Exception:
            return float(default)

    return Settings(
        postgres_dsn=dsn,
        llm_api_base=_cfg("LLM_API_BASE", os.getenv("OPENAI_API_BASE", "http://127.0.0.1:8000/v1")).strip(),
        llm_api_key=_cfg("LLM_API_KEY", os.getenv("OPENAI_API_KEY", "")).strip(),
        llm_model=_cfg("LLM_MODEL", os.getenv("OPENAI_MODEL", "qwen3-next-80b-3card")).strip() or "qwen3-next-80b-3card",
        emb_api_base=_cfg("EMB_API_BASE", "http://127.0.0.1:8000/v1").strip(),
        emb_api_key=_cfg("EMB_API_KEY", os.getenv("OPENAI_API_KEY", "")).strip(),
        emb_model=_cfg("EMB_MODEL", "bge-m3").strip() or "bge-m3",
        hot_tag_min_freq=_cfg_int("HOT_TAG_MIN_FREQ", 5),
        hot_tag_cache_ttl_s=_cfg_int("HOT_TAG_CACHE_TTL_S", 6 * 3600),
        tag_fuzzy_threshold=_cfg_int("TAG_FUZZY_THRESHOLD", 90),
        search_candidates_per_source=_cfg_int("SEARCH_CANDIDATES_PER_SOURCE", 50),
        search_rrf_k=_cfg_int("SEARCH_RRF_K", 60),
        siglip_model=_cfg("SIGLIP_MODEL", "google/siglip-so400m-patch14-384").strip(),
        siglip_device=_cfg("SIGLIP_DEVICE", "cpu").strip() or "cpu",
        rec_profile_days=_cfg_int("REC_PROFILE_DAYS", 30),
        rec_candidate_hours=_cfg_int("REC_CANDIDATE_HOURS", 24),
        rec_cluster_k=_cfg_int("REC_CLUSTER_K", 3),
        rec_cluster_cache_ttl_s=_cfg_int("REC_CLUSTER_CACHE_TTL_S", 900),
        rec_tag_weight=_cfg_float("REC_TAG_WEIGHT", 0.55),
        rec_visual_weight=_cfg_float("REC_VISUAL_WEIGHT", 0.45),
        rec_strictness=_cfg_float("REC_STRICTNESS", 0.55),
        rec_candidate_limit=_cfg_int("REC_CANDIDATE_LIMIT", 400),
        rec_tag_floor_score=_cfg_float("REC_TAG_FLOOR_SCORE", 0.08),
        prompt_search_narrative_system=_cfg("PROMPT_SEARCH_NARRATIVE_SYSTEM", "").strip(),
        prompt_profile_system=_cfg("PROMPT_PROFILE_SYSTEM", "").strip(),
        prompt_report_system=_cfg("PROMPT_REPORT_SYSTEM", "").strip(),
        prompt_tag_extract_system=_cfg("PROMPT_TAG_EXTRACT_SYSTEM", "").strip(),
    )
