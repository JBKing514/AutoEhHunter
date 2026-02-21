from typing import Any

from hunterAgent.skills.profile import run_profile
from hunterAgent.skills.registry import SkillContext, register_skill


PROFILE_SCHEMA = {
    "type": "object",
    "properties": {
        "days": {"type": "integer", "minimum": 1, "maximum": 365},
        "target": {"type": "string", "enum": ["reading", "inventory"]},
    },
}


@register_skill(name="profile", description="Build user profile from reading records", parameters_schema=PROFILE_SCHEMA, builtin=True)
def builtin_profile(context: SkillContext, days: int = 30, target: str = "reading") -> Any:
    return run_profile(
        settings=context.settings,
        llm=context.llm,
        payload={"days": int(days or 30), "target": str(target or "reading"), "use_llm": True},
    )
