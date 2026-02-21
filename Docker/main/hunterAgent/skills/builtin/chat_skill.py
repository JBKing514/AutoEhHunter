from typing import Any

from hunterAgent.skills.chat import run_chat
from hunterAgent.skills.registry import SkillContext, register_skill


CHAT_SCHEMA = {
    "type": "object",
    "properties": {
        "query": {"type": "string", "description": "chat input"},
    },
    "required": ["query"],
}


@register_skill(name="chat", description="General conversation", parameters_schema=CHAT_SCHEMA, builtin=True)
def builtin_chat(context: SkillContext, query: str) -> Any:
    return run_chat(settings=context.settings, llm=context.llm, payload={"query": str(query or "")})
