from pydantic import BaseModel
from typing import Any


class ConversationMessage(BaseModel):
    role: str  # "user" or "assistant"
    content: str


class ParseRequest(BaseModel):
    prompt: str
    user_id: str
    user_resources: list[dict[str, Any]] = []
    conversation_history: list[ConversationMessage] = []


class ParseResponse(BaseModel):
    type: str  # "tool_call", "clarification", "conversation"
    tool: str | None = None
    parameters: dict[str, Any] = {}
    message: str | None = None
    options: list[str] = []


class InterpretRequest(BaseModel):
    user_prompt: str
    tool_name: str
    tool_result: dict[str, Any]
    user_resources: list[dict[str, Any]] = []
    conversation_history: list[ConversationMessage] = []


class InterpretResponse(BaseModel):
    message: str
