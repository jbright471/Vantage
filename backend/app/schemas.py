from pydantic import BaseModel


class NodeResponse(BaseModel):
    node_id: str
    display_name: str
    role: str
    enabled: bool
    created_from: str


class WarningResponse(BaseModel):
    warning_id: str
    warning_type: str
    severity: str
    node_id: str | None = None
    summary: str
