from typing import Any

from hunterAgent.skills.registry import SkillContext, register_skill
from hunterAgent.skills.report import run_report


REPORT_SCHEMA = {
    "type": "object",
    "properties": {
        "type": {"type": "string", "enum": ["daily", "weekly", "monthly", "full"]},
    },
}


@register_skill(name="report", description="Generate reading report", parameters_schema=REPORT_SCHEMA, builtin=True)
def builtin_report(context: SkillContext, type: str = "weekly") -> Any:
    return run_report(settings=context.settings, llm=context.llm, payload={"type": str(type or "weekly")})
