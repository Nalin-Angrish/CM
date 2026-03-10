from pydantic import BaseModel
from typing import Any


class ResourceResponse(BaseModel):
    id: str
    resource_type: str
    cloud_identifier: str | None
    name: str
    region: str | None
    configuration: dict[str, Any]
    status: str
    created_at: str

    class Config:
        from_attributes = True


class ExecutionLogResponse(BaseModel):
    id: str
    action: str
    tool_name: str | None
    tool_params: dict | None
    result: dict | None
    status: str
    error_message: str | None
    duration_ms: int | None
    created_at: str

    class Config:
        from_attributes = True
