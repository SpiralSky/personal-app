"""The shared item shape every source (Brightspace, Outlook, ...) ingests."""

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator

DATE_FIELDS = ("occurred_at", "due_at", "starts_at", "ends_at")


def clean_text(value: Any) -> Any:
    """Recursively make strings valid UTF-8 (mail bodies can carry lone surrogates or NULs)."""
    if isinstance(value, str):
        if value.isascii() and "\x00" not in value:
            return value
        fixed = value.encode("utf-16", "surrogatepass").decode("utf-16", "replace")
        return fixed.replace("\x00", "")
    if isinstance(value, dict):
        return {k: clean_text(v) for k, v in value.items()}
    if isinstance(value, list):
        return [clean_text(v) for v in value]
    return value


def to_utc_iso(value: datetime | str | None) -> str | None:
    """Normalise to 'YYYY-MM-DDTHH:MM:SSZ' so stored dates compare lexically."""
    if value in (None, ""):
        return None
    if isinstance(value, str):
        value = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


class ItemIn(BaseModel):
    source: str = Field(description='Where it came from, e.g. "brightspace:splms" or "outlook"')
    kind: str = Field(description="assignment | quiz | announcement | content | event | grade | course | email ...")
    external_id: str = Field(description="Stable id within source+kind")
    title: str = ""
    body: str = ""
    url: str | None = None
    course_id: str | None = None
    course_name: str | None = None
    occurred_at: str | None = None
    due_at: str | None = None
    starts_at: str | None = None
    ends_at: str | None = None
    # Source-specific fields. Everything except "raw" and "meta" is part of change detection.
    data: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def _clean(cls, values: Any) -> Any:
        return clean_text(values) if isinstance(values, dict) else values

    @field_validator(*DATE_FIELDS, mode="before")
    @classmethod
    def _dates(cls, v: Any) -> str | None:
        return to_utc_iso(v)

    @property
    def id(self) -> str:
        return f"{self.source}:{self.kind}:{self.external_id}"


class IngestRequest(BaseModel):
    items: list[ItemIn]
