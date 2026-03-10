from pydantic import BaseModel
from typing import Any


class ToolRequest(BaseModel):
    tool: str
    parameters: dict[str, Any]
    user_id: str | None = None


class ToolResponse(BaseModel):
    success: bool
    cloud_identifier: str | None = None
    message: str
    details: dict[str, Any] = {}
