"""Cloud-model catalog + chat schemas (white-labeled managed cloud)."""
from __future__ import annotations

from pydantic import BaseModel, Field


class CloudModel(BaseModel):
    id: str
    name: str
    organization: str | None = None
    type: str | None = None
    context_length: int | None = None
    chattable: bool = True


class ChatMessage(BaseModel):
    role: str = Field(pattern="^(system|user|assistant)$")
    content: str = Field(min_length=1)


class CloudChatRequest(BaseModel):
    model: str
    messages: list[ChatMessage] = Field(min_length=1)
    # No upper limit; -1 / 0 = let the model decide.
    max_tokens: int = Field(default=1024, ge=-1)
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)


class CloudChatResponse(BaseModel):
    output: str
    model: str
    tokens_generated: int = 0
    prompt_tokens: int = 0
    path: str = "cloud_managed"
