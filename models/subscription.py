from __future__ import annotations

from pydantic import BaseModel, field_validator


class SubscriptionChange(BaseModel):
    signal_id: str

    @field_validator("signal_id")
    @classmethod
    def validate_signal_id(cls, value: str) -> str:
        signal_id = value.strip()
        if not signal_id:
            raise ValueError("signal_id is required")
        return signal_id
