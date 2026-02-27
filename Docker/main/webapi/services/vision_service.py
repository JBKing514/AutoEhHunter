import importlib.util
import io
import logging
import os
import shutil
import site
import subprocess
import sys
import threading
from datetime import datetime
from pathlib import Path
from typing import Any

from ..core.constants import RUNTIME_DIR
from ..core.runtime_state import model_dl_lock, model_dl_state

logger = logging.getLogger(__name__)

_siglip_runtime_lock = threading.Lock()
_siglip_runtime: dict[str, Any] = {}
# Per-model loading events: other threads wait on the Event instead of
# triggering a second load.  Keyed by model_id.
_siglip_loading_events: dict[str, threading.Event] = {}
_siglip_pydeps_install_lock = threading.Lock()


def _now_iso() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def _models_root() -> Path:
    p = RUNTIME_DIR / "models"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _siglip_root() -> Path:
    p = _models_root() / "siglip"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _folder_size_bytes(root: Path) -> int:
    if not root.exists():
        return 0
    total = 0
    for p in root.rglob("*"):
        if p.is_file():
            try:
                total += int(p.stat().st_size)
            except Exception:
                continue
    return total


def _runtime_pydeps_dir() -> Path:
    p = _models_root() / "pydeps"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _runtime_pip_cache_dir() -> Path:
    p = _models_root() / "pip_cache"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _ensure_runtime_pydeps_path() -> None:
    p = _runtime_pydeps_dir()
    s = str(p)
    if s not in sys.path:
        sys.path.insert(0, s)
    try:
        site.addsitedir(s)
    except Exception:
        pass


def _siglip_env_extra() -> dict[str, str]:
    pydeps = str(_runtime_pydeps_dir())
    base_py = str(os.environ.get("PYTHONPATH") or "")
    py_path = f"{pydeps}{os.pathsep}{base_py}" if base_py else pydeps
    return {
        "HF_HOME": str(_models_root() / "hf_cache"),
        "TRANSFORMERS_CACHE": str(_models_root() / "hf_cache"),
        "PIP_CACHE_DIR": str(_runtime_pip_cache_dir()),
        "PYTHONPATH": py_path,
    }


def _run_cmd(cmd: list[str], env_extra: dict[str, str] | None = None, timeout: int = 3600) -> tuple[int, str, str]:
    env = dict(os.environ)
    if env_extra:
        env.update({k: str(v) for k, v in env_extra.items()})
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, env=env)
    return int(p.returncode), str(p.stdout or ""), str(p.stderr or "")


def _siglip_pip_cmds() -> list[list[str]]:
    target = str(_runtime_pydeps_dir())
    cmds: list[list[str]] = []
    torch_cmd = [
        sys.executable,
        "-m",
        "pip",
        "install",
        "--target",
        target,
        "--upgrade",
        "--force-reinstall",
        "--no-cache-dir",
        "--only-binary",
        ":all:",
    ]
    torch_cmd.extend(["--extra-index-url", "https://download.pytorch.org/whl/cpu"])
    torch_cmd.extend(["torch", "torchvision"])
    cmds.append(torch_cmd)
    deps_cmd = [
        sys.executable,
        "-m",
        "pip",
        "install",
        "--target",
        target,
        "--upgrade",
        "--force-reinstall",
        "--no-cache-dir",
        "--only-binary",
        ":all:",
        "numpy",
        "transformers",
        "sentencepiece",
        "protobuf",
        "pillow",
    ]
    cmds.append(deps_cmd)
    return cmds


def _run_siglip_pip_cmds(cmds: list[list[str]], env_extra: dict[str, str], timeout: int = 7200) -> tuple[int, str, str]:
    all_out: list[str] = []
    all_err: list[str] = []
    for cmd in cmds:
        rc, out, err = _run_cmd(cmd, env_extra=env_extra, timeout=timeout)
        if out:
            all_out.append(out)
        if err:
            all_err.append(err)
        if rc != 0:
            return rc, "\n".join(all_out), "\n".join(all_err)
    return 0, "\n".join(all_out), "\n".join(all_err)


def _verify_siglip_runtime_deps(env_extra: dict[str, str]) -> tuple[bool, str]:
    py = (
        "from pathlib import Path; "
        "import PIL, numpy, torch, transformers; "
        "lib=Path(torch.__file__).resolve().parent/'lib'/'libtorch_global_deps.so'; "
        "print('ok' if lib.exists() else f'missing:{lib}')"
    )
    rc, out, err = _run_cmd([sys.executable, "-c", py], env_extra=env_extra, timeout=300)
    text = (out or "") + ("\n" + err if err else "")
    if rc != 0:
        return False, text.strip()
    if "missing:" in text:
        return False, text.strip()
    return True, text.strip()


def _reinstall_siglip_runtime_deps(env_extra: dict[str, str]) -> None:
    with _siglip_pydeps_install_lock:
        pydeps = _runtime_pydeps_dir()
        if pydeps.exists():
            shutil.rmtree(pydeps, ignore_errors=True)
        pydeps.mkdir(parents=True, exist_ok=True)

        pip_cmds = _siglip_pip_cmds()
        rc, out, err = _run_siglip_pip_cmds(pip_cmds, env_extra=env_extra, timeout=7200)
        if rc != 0:
            raise RuntimeError(f"pip install failed: {err or out}")

        ok, reason = _verify_siglip_runtime_deps(env_extra)
        if not ok:
            raise RuntimeError(f"runtime deps verify failed: {reason}")


def _model_status() -> dict[str, Any]:
    siglip_dir = _siglip_root()
    sz = _folder_size_bytes(siglip_dir)
    config_exists = any((siglip_dir / "models--google--siglip-so400m-patch14-384").rglob("config.json")) if siglip_dir.exists() else False
    blobs_count = len(list(siglip_dir.rglob("blobs/*"))) if siglip_dir.exists() else 0
    pydeps_dir = _runtime_pydeps_dir()
    pydeps_sz = _folder_size_bytes(pydeps_dir)
    _ensure_runtime_pydeps_path()
    deps_ok = all(importlib.util.find_spec(m) is not None for m in ["PIL", "torch", "transformers", "numpy"])
    return {
        "siglip": {
            "path": str(siglip_dir),
            "exists": siglip_dir.exists(),
            "size_bytes": sz,
            "size_mb": round(sz / (1024 * 1024), 2),
            "usable": bool(config_exists and blobs_count > 0 and sz > 50 * 1024 * 1024),
            "blobs": blobs_count,
        },
        "runtime_deps": {
            "path": str(pydeps_dir),
            "size_mb": round(pydeps_sz / (1024 * 1024), 2),
            "ready": deps_ok,
        },
    }


def _check_torch_runtime() -> tuple[bool, str]:
    try:
        import importlib

        torch = importlib.import_module("torch")
        c_mod = importlib.import_module("torch._C")
        c_file = str(getattr(c_mod, "__file__", "") or "")
        if c_file and c_file.endswith((".py", "__init__.py")):
            return False, f"torch._C resolved to python file: {c_file}"
        _ = str(getattr(torch, "__version__", ""))
        return True, "ok"
    except Exception as e:
        return False, str(e)


def _runtime_deps_ready_now() -> tuple[bool, str]:
    _ensure_runtime_pydeps_path()
    need = ["PIL", "torch", "transformers", "numpy"]
    missing = [m for m in need if importlib.util.find_spec(m) is None]
    if missing:
        return False, f"missing modules: {', '.join(missing)}"
    ok_torch, reason_torch = _check_torch_runtime()
    if not ok_torch:
        return False, f"torch runtime invalid: {reason_torch}"
    return True, "ok"


def _ensure_siglip_runtime_deps() -> None:
    ok, reason = _runtime_deps_ready_now()
    if ok:
        return
    raise RuntimeError(
        "siglip runtime deps not ready: "
        f"{reason}. "
        "Please run SigLIP download/install first."
    )


def _set_dl_state(task_id: str, patch: dict[str, Any]) -> None:
    with model_dl_lock:
        base = dict(model_dl_state.get(task_id) or {})
        base.update(patch)
        model_dl_state[task_id] = base


def _append_dl_log(task_id: str, line: str) -> None:
    with model_dl_lock:
        st = dict(model_dl_state.get(task_id) or {})
        logs = list(st.get("logs") or [])
        logs.append(str(line))
        st["logs"] = logs[-200:]
        model_dl_state[task_id] = st


def _download_siglip_worker(task_id: str, model_id: str) -> None:
    try:
        _set_dl_state(task_id, {"status": "running", "progress": 5, "stage": "install_deps", "started_at": _now_iso()})
        siglip_dir = _siglip_root()
        env_extra = _siglip_env_extra()
        env_extra["HF_HUB_DISABLE_TELEMETRY"] = "1"
        _reinstall_siglip_runtime_deps(env_extra)

        _set_dl_state(task_id, {"progress": 45, "stage": "download_processor"})
        py_p = (
            "from transformers import AutoProcessor; "
            f"AutoProcessor.from_pretrained('{model_id}', cache_dir=r'{siglip_dir.as_posix()}'); print('processor_ok')"
        )
        rc_p, out_p, err_p = _run_cmd([sys.executable, "-c", py_p], env_extra=env_extra, timeout=7200)
        _append_dl_log(task_id, out_p[-1200:] if out_p else "")
        _append_dl_log(task_id, err_p[-1200:] if err_p else "")
        if rc_p != 0:
            raise RuntimeError(f"processor download failed: {err_p or out_p}")

        _set_dl_state(task_id, {"progress": 70, "stage": "download_model"})
        py_m = (
            "from transformers import AutoModel; "
            f"AutoModel.from_pretrained('{model_id}', cache_dir=r'{siglip_dir.as_posix()}'); print('model_ok')"
        )
        rc_m, out_m, err_m = _run_cmd([sys.executable, "-c", py_m], env_extra=env_extra, timeout=7200)
        _append_dl_log(task_id, out_m[-1200:] if out_m else "")
        _append_dl_log(task_id, err_m[-1200:] if err_m else "")
        if rc_m != 0:
            raise RuntimeError(f"model download failed: {err_m or out_m}")

        status = _model_status()
        usable = bool(((status.get("siglip") or {}).get("usable")))
        _set_dl_state(
            task_id,
            {
                "status": "done" if usable else "failed",
                "progress": 100 if usable else 95,
                "stage": "completed" if usable else "verify_failed",
                "error": "" if usable else "download finished but model not marked usable",
                "finished_at": _now_iso(),
                "model_status": status,
            },
        )
    except Exception as e:
        _set_dl_state(task_id, {"status": "failed", "stage": "error", "error": str(e), "finished_at": _now_iso()})


def _clear_siglip_runtime() -> dict[str, Any]:
    siglip_dir = _siglip_root()
    before = _folder_size_bytes(siglip_dir)
    if siglip_dir.exists():
        shutil.rmtree(siglip_dir, ignore_errors=True)
    siglip_dir.mkdir(parents=True, exist_ok=True)
    return {
        "ok": True,
        "freed_bytes": before,
        "freed_mb": round(before / (1024 * 1024), 2),
        "status": _model_status(),
    }


def _clear_runtime_pydeps() -> dict[str, Any]:
    p = _runtime_pydeps_dir()
    before = _folder_size_bytes(p)
    if p.exists():
        shutil.rmtree(p, ignore_errors=True)
    p.mkdir(parents=True, exist_ok=True)
    return {"ok": True, "freed_bytes": before, "freed_mb": round(before / (1024 * 1024), 2), "status": _model_status()}


def _flatten_floats(values: Any) -> list[float]:
    out: list[float] = []
    if isinstance(values, (list, tuple)):
        for v in values:
            out.extend(_flatten_floats(v))
        return out
    try:
        out.append(float(values))
    except Exception:
        return []
    return out


def _extract_tensor_like(obj: Any) -> Any:
    if obj is None:
        return None
    if hasattr(obj, "detach"):
        return obj
    if isinstance(obj, dict):
        for k in ("image_embeds", "last_hidden_state", "pooler_output", "logits"):
            if k in obj:
                t = _extract_tensor_like(obj.get(k))
                if t is not None:
                    return t
        for v in obj.values():
            t = _extract_tensor_like(v)
            if t is not None:
                return t
        return None
    for attr in ("image_embeds", "last_hidden_state", "pooler_output", "logits"):
        if hasattr(obj, attr):
            t = _extract_tensor_like(getattr(obj, attr))
            if t is not None:
                return t
    if isinstance(obj, (tuple, list)):
        for v in obj:
            t = _extract_tensor_like(v)
            if t is not None:
                return t
    return None


def _siglip_device() -> str:
    """Return the configured SigLIP compute device (e.g. 'cpu', 'cuda', 'cuda:0')."""
    try:
        from .config_service import resolve_config
        cfg, _ = resolve_config()
        return str(cfg.get("SIGLIP_DEVICE") or "cpu").strip() or "cpu"
    except Exception:
        return "cpu"


def _ensure_siglip_runtime_loaded(model_id: str) -> tuple[Any, Any, Any, Any, str]:
    key = str(model_id or "").strip()
    if not key:
        raise RuntimeError("empty siglip model id")

    # Fast path: already loaded (no lock needed for read after initial store).
    entry = _siglip_runtime.get(key)
    if entry is not None:
        return entry["torch"], entry["model"], entry["processor"], entry["tokenizer"], entry["device"]

    # Slow path: need to load.  Use a per-key Event so that only one thread
    # does the actual load; all others wait for it to finish.
    with _siglip_runtime_lock:
        # Re-check after acquiring lock (another thread may have loaded it
        # while we were waiting).
        entry = _siglip_runtime.get(key)
        if entry is not None:
            return entry["torch"], entry["model"], entry["processor"], entry["tokenizer"], entry["device"]

        if key in _siglip_loading_events:
            # Another thread is already loading; grab its event and wait outside
            # the lock so we don't block other threads unnecessarily.
            event = _siglip_loading_events[key]
        else:
            # We are the designated loader thread.
            event = threading.Event()
            _siglip_loading_events[key] = event
            event = None  # Signal to the code below that we own the load.

    if event is not None:
        # We are a waiting thread — block until the loader thread signals done.
        event.wait(timeout=300)
        entry = _siglip_runtime.get(key)
        if entry is None:
            raise RuntimeError(f"siglip model load failed for '{key}' (loader thread reported error)")
        return entry["torch"], entry["model"], entry["processor"], entry["tokenizer"], entry["device"]

    # We are the loader thread.
    load_error: Exception | None = None
    try:
        _ensure_siglip_runtime_deps()
        try:
            ok_torch, reason_torch = _check_torch_runtime()
            if not ok_torch:
                raise RuntimeError(reason_torch)
            import torch
            from transformers import AutoModel, AutoProcessor, AutoTokenizer
        except Exception as e:
            raise RuntimeError(f"siglip runtime dependencies missing: {e}")

        device = _siglip_device()
        siglip_dir = _siglip_root()
        processor = AutoProcessor.from_pretrained(key, cache_dir=str(siglip_dir), local_files_only=True)
        tokenizer = AutoTokenizer.from_pretrained(key, cache_dir=str(siglip_dir), local_files_only=True)
        model = AutoModel.from_pretrained(key, cache_dir=str(siglip_dir), local_files_only=True)
        model = model.to(device)
        model.eval()

        with _siglip_runtime_lock:
            _siglip_runtime[key] = {
                "torch": torch,
                "model": model,
                "processor": processor,
                "tokenizer": tokenizer,
                "device": device,
            }
    except Exception as e:
        load_error = e
    finally:
        # Always signal waiters, whether load succeeded or failed.
        with _siglip_runtime_lock:
            ev = _siglip_loading_events.pop(key, None)
        if ev is not None:
            ev.set()

    if load_error is not None:
        raise load_error

    entry = _siglip_runtime[key]
    return entry["torch"], entry["model"], entry["processor"], entry["tokenizer"], entry["device"]


def siglip_warmup_ready(model_id: str | None = None) -> tuple[bool, str]:
    target = str(model_id or "google/siglip-so400m-patch14-384").strip()
    st = _model_status()
    siglip_ok = bool(((st.get("siglip") or {}).get("usable")))
    deps_ok = bool(((st.get("runtime_deps") or {}).get("ready")))
    if not deps_ok:
        return False, "runtime_deps_not_ready"
    if not siglip_ok:
        return False, "siglip_model_not_ready"
    return True, target


def warmup_siglip_model(model_id: str | None = None, strict: bool = False, silent_skip: bool = False) -> dict[str, Any]:
    target = str(model_id or "google/siglip-so400m-patch14-384").strip()
    try:
        _ensure_siglip_runtime_loaded(target)
        return {"ok": True, "model_id": target, "loaded": True}
    except Exception as e:
        if strict:
            raise
        if not silent_skip:
            logger.warning("siglip warmup skipped: %s", e)
        return {"ok": False, "model_id": target, "loaded": False, "error": str(e)}


def _embed_image_siglip(image_bytes: bytes, model_id: str) -> list[float]:
    if not image_bytes:
        return []
    try:
        from PIL import Image
        import numpy as _np
    except Exception as e:
        raise RuntimeError(f"siglip runtime dependencies missing: {e}")

    torch, model, processor, _tokenizer, device = _ensure_siglip_runtime_loaded(model_id)
    image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    inputs = processor(images=image, return_tensors="pt")
    inputs = {k: v.to(device) for k, v in inputs.items()}
    with torch.no_grad():
        if hasattr(model, "get_image_features"):
            out = model.get_image_features(**inputs)
        else:
            out = model(**inputs)
        if isinstance(out, torch.Tensor):
            feats = out
        elif hasattr(out, "pooler_output") and getattr(out, "pooler_output") is not None:
            feats = getattr(out, "pooler_output")
        elif isinstance(out, dict) and "image_embeds" in out:
            feats = out["image_embeds"]
        elif isinstance(out, dict) and "last_hidden_state" in out:
            feats = out["last_hidden_state"]
        else:
            out_t = _extract_tensor_like(out)
            if out_t is None or not hasattr(out_t, "detach"):
                raise RuntimeError(f"siglip output tensor unavailable: type={type(out)}")
            feats = out_t
        out_t = feats.detach().cpu().float()
        if out_t.dim() == 3:
            out_t = out_t.mean(dim=1)
        if out_t.dim() == 2:
            out_t = out_t[0]
        if out_t.dim() != 1:
            out_t = out_t.reshape(-1)
        vec = out_t.numpy()
        norm = float(_np.linalg.norm(vec)) + 1e-12
        vec = vec / norm
    return _flatten_floats(vec.tolist())


def _embed_text_siglip(text: str, model_id: str) -> list[float]:
    q = str(text or "").strip()
    if not q:
        return []
    try:
        import numpy as _np
    except Exception as e:
        raise RuntimeError(f"siglip text runtime dependencies missing: {e}")

    torch, model, _processor, tokenizer, device = _ensure_siglip_runtime_loaded(model_id)
    inputs = tokenizer([q], padding=True, truncation=True, return_tensors="pt")
    if "token_type_ids" in inputs:
        inputs.pop("token_type_ids", None)
    inputs = {k: v.to(device) for k, v in inputs.items()}
    with torch.no_grad():
        if hasattr(model, "get_text_features"):
            out = model.get_text_features(**inputs)
        else:
            out = model(**inputs)
        if isinstance(out, torch.Tensor):
            feats = out
        elif hasattr(out, "text_embeds") and getattr(out, "text_embeds") is not None:
            feats = getattr(out, "text_embeds")
        elif hasattr(out, "pooler_output") and getattr(out, "pooler_output") is not None:
            feats = getattr(out, "pooler_output")
        else:
            out_t = _extract_tensor_like(out)
            if out_t is None or not hasattr(out_t, "detach"):
                raise RuntimeError(f"siglip text output tensor unavailable: type={type(out)}")
            feats = out_t
        out_t = feats.detach().cpu().float()
        if out_t.dim() == 2:
            out_t = out_t[0]
        if out_t.dim() != 1:
            out_t = out_t.reshape(-1)
        vec = out_t.numpy()
        norm = float(_np.linalg.norm(vec)) + 1e-12
        vec = vec / norm
    return _flatten_floats(vec.tolist())
