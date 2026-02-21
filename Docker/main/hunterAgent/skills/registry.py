import asyncio
import inspect
from dataclasses import dataclass
from typing import Any, Callable, Dict


SKILL_REGISTRY: Dict[str, Dict[str, Any]] = {}


@dataclass
class SkillContext:
    settings: Any
    llm: Any
    emb: Any
    config: dict
    db_session: Any = None
    lrr_client: Any = None


def register_skill(name: str, description: str, parameters_schema: dict, builtin: bool = False):
    def decorator(func: Callable):
        SKILL_REGISTRY[name] = {
            "name": name,
            "func": func,
            "builtin": bool(builtin),
            "tool_definition": {
                "type": "function",
                "function": {
                    "name": name,
                    "description": description,
                    "parameters": parameters_schema,
                },
            },
        }
        return func

    return decorator


def list_tools() -> list[dict[str, Any]]:
    return [v["tool_definition"] for v in SKILL_REGISTRY.values()]


def list_skills() -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for name, meta in SKILL_REGISTRY.items():
        out.append(
            {
                "name": name,
                "builtin": bool(meta.get("builtin")),
                "description": (((meta.get("tool_definition") or {}).get("function") or {}).get("description") or ""),
            }
        )
    out.sort(key=lambda x: (0 if x["builtin"] else 1, x["name"]))
    return out


def run_skill(name: str, context: SkillContext, kwargs: dict[str, Any]) -> Any:
    if name not in SKILL_REGISTRY:
        raise KeyError(f"unknown skill: {name}")
    fn = SKILL_REGISTRY[name]["func"]
    if inspect.iscoroutinefunction(fn):
        return asyncio.run(fn(context=context, **(kwargs or {})))
    return fn(context=context, **(kwargs or {}))
