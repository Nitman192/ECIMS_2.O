from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from app.models.user import UserRole


class UserOut(BaseModel):
    id: int
    username: str
    role: UserRole
    is_active: bool
    created_at: datetime
