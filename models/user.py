from __future__ import annotations

from pydantic import BaseModel, field_validator


class UserCreate(BaseModel):
    username: str

    @field_validator("username")
    @classmethod
    def validate_username(cls, value: str) -> str:
        username = value.strip()
        if not username:
            raise ValueError("username is required")
        if len(username) > 64:
            raise ValueError("username must be <= 64 characters")
        if any(ch.isspace() for ch in username):
            raise ValueError("username cannot contain spaces")
        return username
