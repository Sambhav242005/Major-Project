from pydantic import BaseModel


class MCPConnectionCreate(BaseModel):
    name: str
    direction: str
    endpoint_url: str | None = None
    auth_config: dict | None = None


class MCPConnectionOut(BaseModel):
    id: str
    name: str
    direction: str
    endpoint_url: str | None
    status: str


class MCPConnectionListResponse(BaseModel):
    connections: list[MCPConnectionOut]


class MCPOAuthAuthorizeResponse(BaseModel):
    authorization_url: str
    state: str


class MCPOAuthCallbackResponse(BaseModel):
    status: str
    expires_at: float


class MCPTokenStatusResponse(BaseModel):
    has_token: bool
    expired: bool | None = None
    expires_at: str | None = None
    scope: str | None = None
