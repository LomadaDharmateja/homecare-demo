"""Pydantic models. ExtractedFields doubles as the JSON schema passed to Ollama's `format`."""
from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field

ServiceType = Literal["shopping", "transport", "companionship", "household", "other"]
Urgency = Literal["low", "medium", "high"]
ContactTime = Literal["morning", "afternoon", "evening"]
MissingItem = Literal["location", "date", "details"]


class IntakeIn(BaseModel):
    text: str = Field(min_length=1)
    channel: Literal["web_form", "email"] = "web_form"
    received_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ExtractedFields(BaseModel):
    # Field order matters: the model fills when_needed before deciding urgency.
    service_type: ServiceType
    when_needed: str | None
    urgency: Urgency
    callback_requested: bool
    preferred_contact_time: ContactTime | None
    location: str | None
    summary: str
    # Not asked from the model: check_missing_info derives it with fixed rules (see tools.py).
    missing_info: list[MissingItem] = Field(default_factory=list)

    @classmethod
    def model_schema_for_llm(cls) -> dict:
        schema = cls.model_json_schema()
        schema["properties"].pop("missing_info")
        return schema


class AgentDecision(BaseModel):
    # The enum is narrowed at runtime to the tools that have not run yet (see agent.py).
    tool: str
    reason: str


class FollowupDraft(BaseModel):
    message: str
