from pydantic import BaseModel, Field
from typing import Any


class ConversationMessage(BaseModel):
    role: str  # "user" or "assistant"
    content: str


class PromptRequest(BaseModel):
    prompt: str = Field(min_length=1, max_length=2000)
    conversation_history: list[ConversationMessage] = []


class PromptResponse(BaseModel):
    prompt_id: str
    status: str  # "completed", "failed", "denied", "clarification", "conversation"
    response_type: str = "tool_result"  # "tool_result", "clarification", "conversation"
    parsed_action: dict | None = None
    result: dict | None = None
    message: str | None = None
    options: list[str] = []
    error: str | None = None

    class Config:
        from_attributes = True
