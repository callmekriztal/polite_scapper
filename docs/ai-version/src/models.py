from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, HttpUrl, field_validator

class BookRecord(BaseModel):
    title: str = Field(..., min_length=1, description="Non-empty book title")
    product_url: HttpUrl = Field(..., description="Absolute URL of product detail page")
    price_text: str = Field(..., description="Raw price text scraped from page")
    price_gbp: float = Field(..., ge=0.0, description="Normalized price in GBP")
    availability_text: str = Field(..., description="Raw availability text")
    rating_text: str = Field(..., description="Raw rating text e.g. Three")
    description: Optional[str] = Field(default=None, description="Book description or null")
    source_page: HttpUrl = Field(..., description="Catalogue source page URL")
    fetched_at: str = Field(..., description="ISO-8601 UTC timestamp")

    @field_validator("title")
    @classmethod
    def validate_title_non_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Title must be non-empty")
        return v.strip()

    @field_validator("fetched_at")
    @classmethod
    def validate_iso_timestamp(cls, v: str) -> str:
        try:
            datetime.fromisoformat(v)
            return v
        except Exception as e:
            raise ValueError(f"Invalid ISO-8601 timestamp: {v}") from e
