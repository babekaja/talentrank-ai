from typing import Annotated

from pydantic import BaseModel, ConfigDict, EmailStr, Field, StringConstraints


AccountName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=180)]


class RegisterRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')

    full_name: AccountName
    organization_name: AccountName
    organization_slug: str = Field(pattern=r'^[a-z0-9-]{2,80}$')
    email: EmailStr = Field(max_length=254)
    password: str = Field(min_length=12, max_length=256)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1)
    organization_slug: str = Field(pattern=r'^[a-z0-9-]{2,80}$')
    remember_me: bool = False


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = 'bearer'
    expires_in: int = 900


class DemoLoginRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')


class MeResponse(BaseModel):
    id: str
    full_name: str
    email: EmailStr
    organization_id: str
    organization_name: str
    organization_slug: str
    role: str
    demo_mode: bool = False
    demo_read_only: bool = False


class OrganizationSummary(BaseModel):
    id: str
    name: str
    slug: str
    active_members: int
