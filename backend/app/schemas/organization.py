import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models import Role


class OrganizationCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)


class OrganizationRead(BaseModel):
    id: uuid.UUID
    name: str
    slug: str
    role: str = Field(description="Your role in this organization")
    created_at: datetime


class MemberAdd(BaseModel):
    email: EmailStr
    role: Role = Role.MEMBER


class MemberRead(BaseModel):
    user_id: uuid.UUID
    email: str
    full_name: str | None
    role: str
    created_at: datetime


class WorkspaceCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=2000)


class WorkspaceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID
    name: str
    description: str | None
    created_at: datetime
