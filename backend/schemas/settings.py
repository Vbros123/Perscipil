"""Settings schemas."""
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class SettingsUpdate(BaseModel):
    default_view: str | None = Field(default=None, max_length=40)
    risk_threshold: int | None = Field(default=None, ge=0, le=1000)
    email_alerts: bool | None = None
    weekly_digest: bool | None = None
    simulated_data_labels: bool | None = None


class SettingsOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    default_view: str
    risk_threshold: int
    email_alerts: bool
    weekly_digest: bool
    simulated_data_labels: bool
    created_at: datetime
    updated_at: datetime
