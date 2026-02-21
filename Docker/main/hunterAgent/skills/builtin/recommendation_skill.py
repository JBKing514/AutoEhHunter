from typing import Any

from hunterAgent.skills.recommendation import run_recommendation
from hunterAgent.skills.registry import SkillContext, register_skill


RECOMMEND_SCHEMA = {
    "type": "object",
    "properties": {
        "k": {"type": "integer", "minimum": 1, "maximum": 50},
    },
}


@register_skill(name="recommendation", description="Recommend new EH works", parameters_schema=RECOMMEND_SCHEMA, builtin=True)
def builtin_recommendation(context: SkillContext, k: int = 10) -> Any:
    return run_recommendation(settings=context.settings, llm=context.llm, payload={"k": int(k or 10)})
