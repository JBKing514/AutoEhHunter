from typing import Any

from pydantic import BaseModel, Field


class ConfigUpdateRequest(BaseModel):
    values: dict[str, Any] = Field(default_factory=dict)


class ScheduleUpdateRequest(BaseModel):
    schedule: dict[str, dict[str, Any]]


class TaskRunRequest(BaseModel):
    task: str
    args: str = ""


class ProviderModelsRequest(BaseModel):
    base_url: str = ""
    api_key: str = ""


class HomeImageSearchRequest(BaseModel):
    arcid: str = ""
    gid: int | None = None
    token: str = ""
    scope: str = "both"
    limit: int = 24
    include_categories: list[str] = []
    include_tags: list[str] = []


class HomeTextSearchRequest(BaseModel):
    query: str = ""
    scope: str = "both"
    limit: int = 24
    use_llm: bool = False
    ui_lang: str = "zh"
    include_categories: list[str] = []
    include_tags: list[str] = []


class HomeHybridSearchRequest(BaseModel):
    query: str = ""
    arcid: str = ""
    gid: int | None = None
    token: str = ""
    scope: str = "both"
    limit: int = 24
    text_weight: float | None = None
    visual_weight: float | None = None
    use_llm: bool = False
    ui_lang: str = "zh"
    include_categories: list[str] = []
    include_tags: list[str] = []


class RecommendTouchRequest(BaseModel):
    gid: int | None = None
    token: str = ""
    eh_url: str = ""
    ex_url: str = ""
    weight: float = 1.0


class RecommendImpressionItem(BaseModel):
    gid: int | None = None
    token: str = ""
    eh_url: str = ""
    ex_url: str = ""


class RecommendImpressionBatchRequest(BaseModel):
    items: list[RecommendImpressionItem] = []
    weight: float = 1.0


class ChatMessageRequest(BaseModel):
    session_id: str = "default"
    text: str = ""
    image_arcid: str = ""
    mode: str = "chat"
    intent: str = "auto"
    ui_lang: str = "zh"
    context: dict[str, Any] | None = None


class ChatMessageEditRequest(BaseModel):
    session_id: str = "default"
    index: int = 0
    text: str = ""
    regenerate: bool = False


class ChatMessageDeleteRequest(BaseModel):
    session_id: str = "default"
    index: int = 0


class AuthRegisterRequest(BaseModel):
    username: str = ""
    password: str = ""


class AuthLoginRequest(BaseModel):
    username: str = ""
    password: str = ""


class AuthUpdateProfileRequest(BaseModel):
    username: str = ""


class AuthChangePasswordRequest(BaseModel):
    username: str = ""
    old_password: str = ""
    new_password: str = ""


class AuthDeleteAccountRequest(BaseModel):
    password: str = ""


class SetupValidateDbRequest(BaseModel):
    host: str = ""
    port: int = 5432
    db: str = ""
    user: str = ""
    password: str = ""
    sslmode: str = "prefer"


class SetupValidateLrrRequest(BaseModel):
    base: str = ""
    api_key: str = ""
