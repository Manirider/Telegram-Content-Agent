"""Google Sheets schemas and constants."""
from dataclasses import dataclass
from datetime import datetime, timezone

REQUIRED_HEADERS = [
    "SourceIdentifier",
    "SubmissionTimestamp",
    "ContentType",
    "LLMTitle",
    "Rationale",
    "Category",
    "X_Variant",
    "LinkedIn_Variant",
]

CONTENT_TYPE_VALUES = {"text", "url", "pdf"}


@dataclass
class SheetsRow:
    """Row data for Google Sheets."""
    source_identifier: str
    submission_timestamp: datetime
    content_type: str
    llm_title: str
    rationale: str
    category: str
    x_variant: str
    linkedin_variant: str
    
    def to_list(self) -> list:
        """Convert to list for Sheets append."""
        return [
            self.source_identifier,
            self.submission_timestamp.isoformat(),
            self.content_type,
            self.llm_title,
            self.rationale,
            self.category,
            self.x_variant,
            self.linkedin_variant,
        ]
    
    @classmethod
    def from_generation(
        cls,
        source_identifier: str,
        content_type: str,
        title: str,
        rationale: str,
        category: str,
        x_variant: str,
        linkedin_variant: str,
    ) -> "SheetsRow":
        """Create from generation result."""
        return cls(
            source_identifier=source_identifier,
            submission_timestamp=datetime.now(timezone.utc),
            content_type=content_type,
            llm_title=title,
            rationale=rationale,
            category=category,
            x_variant=x_variant,
            linkedin_variant=linkedin_variant,
        )


@dataclass
class SheetsConfig:
    """Google Sheets configuration."""
    credentials_b64: str
    spreadsheet_id: str
    worksheet_name: str = "Content"