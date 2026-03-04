from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from app.models.user import UserRole


class UserOut(BaseModel):
    id: int
    username: str
    role: UserRole
    is_active: bool
    created_at: datetime
    updated_at: datetime | None = None
    last_login_at: datetime | None = None
    must_reset_password: bool = False


class AdminUserCreateRequest(BaseModel):
    username: str = Field(min_length=3, max_length=128)
    password: str = Field(min_length=12, max_length=256)
    role: UserRole
    is_active: bool = True
    must_reset_password: bool = True


class AdminUserRoleUpdateRequest(BaseModel):
    role: UserRole


class AdminUserActiveUpdateRequest(BaseModel):
    is_active: bool
    reason: str = Field(min_length=1, max_length=512)


class AdminUserResetPasswordRequest(BaseModel):
    new_password: str = Field(min_length=12, max_length=256)
    must_reset_password: bool = True
    reason: str = Field(min_length=1, max_length=512)


class SelfPasswordResetRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=256)
    new_password: str = Field(min_length=12, max_length=256)
