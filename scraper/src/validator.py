from typing import Any
from pydantic import ValidationError
from src.models import BookRecord, PageRecord

class RecordValidator:
    """Validates raw extracted records against Pydantic schema."""

    @staticmethod
    def validate_record(raw_record: dict[str, Any]) -> tuple[BookRecord | None, dict[str, Any] | None]:
        """Validate a book record (book mode)."""
        return RecordValidator._validate(raw_record, BookRecord, "BookRecord")

    @staticmethod
    def validate_page(raw_record: dict[str, Any]) -> tuple[PageRecord | None, dict[str, Any] | None]:
        """Validate a page record (generic mode)."""
        return RecordValidator._validate(raw_record, PageRecord, "PageRecord")

    @staticmethod
    def _validate(
        raw_record: dict[str, Any],
        model: type,
        label: str,
    ) -> tuple[Any | None, dict[str, Any] | None]:
        """
        Validate a single raw record against a Pydantic model.
        Returns (validated_record, error_details).
        If valid, error_details is None.
        If invalid, validated_record is None and error_details contains failure context.
        """
        try:
            validated = model.model_validate(raw_record)
            return validated, None
        except ValidationError as ve:
            error_details = {
                "product_url": raw_record.get("product_url") or raw_record.get("url"),
                "reason": f"{label} Schema Validation Failed",
                "validation_errors": ve.errors(include_url=False),
                "raw_record": raw_record
            }
            return None, error_details
        except Exception as ex:
            error_details = {
                "product_url": raw_record.get("product_url") or raw_record.get("url"),
                "reason": str(ex),
                "raw_record": raw_record
            }
            return None, error_details
