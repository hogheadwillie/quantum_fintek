from uuid import UUID

from pydantic import BaseModel, ConfigDict, field_validator

from app.identity.normalization import normalize_email as normalize_email_value


class LoginRequest(BaseModel):
    organization_slug: str
    email: str
    password: str

    @field_validator("email")
    @classmethod
    def normalize_email(cls, email: str) -> str:
        return normalize_email_value(email)


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
