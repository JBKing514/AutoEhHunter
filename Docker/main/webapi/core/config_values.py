from typing import Any

from .constants import CONFIG_SPECS


def str_bool(value: bool) -> str:
    return "1" if bool(value) else "0"


def as_bool(value: Any, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in ("1", "true", "yes", "y", "on")


def normalize_value(key: str, raw: Any) -> str:
    spec = CONFIG_SPECS.get(key, {"type": "text", "default": ""})
    kind = str(spec.get("type", "text"))
    default = spec.get("default", "")
    if kind == "bool":
        return str_bool(as_bool(raw, bool(default)))
    if kind == "int":
        try:
            number = int(str(raw).strip())
        except Exception:
            number = int(default)
        number = max(int(spec.get("min", number)), min(int(spec.get("max", number)), number))
        return str(number)
    if kind == "float":
        try:
            number = float(str(raw).strip())
        except Exception:
            number = float(default)
        number = max(float(spec.get("min", number)), min(float(spec.get("max", number)), number))
        return str(number)
    if raw is None:
        return str(default)
    return str(raw).strip()
