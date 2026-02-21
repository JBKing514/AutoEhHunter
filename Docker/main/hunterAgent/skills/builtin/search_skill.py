from typing import Any

from hunterAgent.skills.registry import SkillContext, register_skill
from hunterAgent.skills.search import run_search


SEARCH_SCHEMA = {
    "type": "object",
    "properties": {
        "query": {"type": "string", "description": "search keywords"},
        "mode": {"type": "string", "enum": ["auto", "plot", "visual", "mixed"]},
        "k": {"type": "integer", "minimum": 1, "maximum": 50},
    },
    "required": ["query"],
}


@register_skill(name="search", description="Search gallery in local/eh data", parameters_schema=SEARCH_SCHEMA, builtin=True)
def builtin_search(context: SkillContext, query: str, mode: str = "auto", k: int = 10) -> Any:
    return run_search(
        settings=context.settings,
        llm=context.llm,
        emb=context.emb,
        payload={"query": str(query or ""), "mode": str(mode or "auto"), "k": int(k or 10)},
    )
