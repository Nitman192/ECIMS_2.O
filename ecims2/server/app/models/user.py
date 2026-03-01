from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class UserRole(str, Enum):
    ADMIN = "ADMIN"
    ANALYST = "ANALYST"
    VIEWER = "VIEWER"


@dataclass(frozen=True)
class User:
    id: int
    username: str
    password_hash: str
    role: UserRole
    is_active: bool
    created_at: datetime
