from uuid import UUID

from pydantic import BaseModel, ConfigDict


class LoginRequest(BaseModel):
    organization_slug: str
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    organization_id: UUID
    email: str
    is_active: bool
    is_superuser: bool
