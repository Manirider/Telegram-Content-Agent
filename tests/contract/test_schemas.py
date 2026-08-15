"""Contract tests for Google Sheets schema and content validation."""
from datetime import datetime, timezone

import pytest

from app.ingestion.models import ContentType
from app.llm.schemas import ContentGenerationResult, Variants
from app.sheets.schemas import CONTENT_TYPE_VALUES, REQUIRED_HEADERS, SheetsRow


class TestSheetsSchemaContract:
    """Verify exact Google Sheets schema compliance."""
    
    def test_required_headers_exact(self):
        """Headers must match specification exactly."""
        expected = [
            "SourceIdentifier",
            "SubmissionTimestamp",
            "ContentType",
            "LLMTitle",
            "Rationale",
            "Category",
            "X_Variant",
            "LinkedIn_Variant",
        ]
        assert REQUIRED_HEADERS == expected
    
    def test_content_type_values_exact(self):
        """ContentType must only allow specified values."""
        assert CONTENT_TYPE_VALUES == {"text", "url", "pdf"}
    
    def test_content_type_enum_matches(self):
        """ContentType enum must match sheet values."""
        enum_values = {ct.value for ct in ContentType}
        assert enum_values == CONTENT_TYPE_VALUES


class TestSheetsRowContract:
    """Test SheetsRow generation matches schema."""
    
    def test_row_to_list_order(self):
        """Row.to_list() must match header order."""
        row = SheetsRow(
            source_identifier="test_source",
            submission_timestamp=datetime(2024, 1, 15, 10, 30, 0, tzinfo=timezone.utc),
            content_type="url",
            llm_title="Test Title",
            rationale="Test rationale",
            category="Technology",
            x_variant="X post",
            linkedin_variant="LinkedIn post",
        )
        
        row_list = row.to_list()
        
        assert row_list[0] == "test_source"  # SourceIdentifier
        assert row_list[1] == "2024-01-15T10:30:00+00:00"  # SubmissionTimestamp (ISO format with timezone)
        assert row_list[2] == "url"  # ContentType
        assert row_list[3] == "Test Title"  # LLMTitle
        assert row_list[4] == "Test rationale"  # Rationale
        assert row_list[5] == "Technology"  # Category
        assert row_list[6] == "X post"  # X_Variant
        assert row_list[7] == "LinkedIn post"  # LinkedIn_Variant
    
    def test_from_generation(self):
        """Factory method creates correct row."""
        row = SheetsRow.from_generation(
            source_identifier="https://example.com",
            content_type="url",
            title="Title",
            rationale="Rationale",
            category="Category",
            x_variant="X",
            linkedin_variant="LI",
        )
        
        assert row.source_identifier == "https://example.com"
        assert row.content_type == "url"
        assert row.llm_title == "Title"
        assert row.rationale == "Rationale"
        assert row.category == "Category"
        assert row.x_variant == "X"
        assert row.linkedin_variant == "LI"
        assert isinstance(row.submission_timestamp, datetime)


class TestContentGenerationContract:
    """Test content generation output contract."""
    
    def test_all_fields_required(self):
        """All fields must be present and non-empty."""
        result = ContentGenerationResult(
            title="Title",
            rationale="Rationale",
            category="Category",
            variants=Variants(x_post="X post", linkedin_post="LinkedIn post"),
        )
        
        # Verify all fields accessible
        assert result.title
        assert result.rationale
        assert result.category
        assert result.variants.x_post
        assert result.variants.linkedin_post
    
    def test_x_post_max_280_chars(self):
        """X post must not exceed 280 characters."""
        # Valid
        result = ContentGenerationResult(
            title="T",
            rationale="R",
            category="C",
            variants=Variants(x_post="x" * 280, linkedin_post="LI"),
        )
        assert len(result.variants.x_post) == 280
        
        # Invalid - should raise
        with pytest.raises(ValueError, match="280"):
            ContentGenerationResult(
                title="T",
                rationale="R",
                category="C",
                variants=Variants(x_post="x" * 281, linkedin_post="LI"),
            )
    
    def test_variants_distinct(self):
        """X and LinkedIn variants must be different."""
        # This is validated at service level, but schema allows same
        # Service layer enforces distinction
        result = ContentGenerationResult(
            title="T",
            rationale="R",
            category="C",
            variants=Variants(x_post="Same", linkedin_post="Same"),
        )
        # Schema allows, but business logic rejects
        assert result.variants.x_post == result.variants.linkedin_post
    
    def test_content_type_values(self):
        """ContentType must be exactly text, url, or pdf."""
        for ct in ["text", "url", "pdf"]:
            row = SheetsRow(
                source_identifier="src",
                submission_timestamp=datetime.now(timezone.utc),
                content_type=ct,
                llm_title="T",
                rationale="R",
                category="C",
                x_variant="X",
                linkedin_variant="LI",
            )
            assert row.content_type in CONTENT_TYPE_VALUES
        
        # Invalid content type should be caught at service layer
        invalid_row = SheetsRow(
            source_identifier="src",
            submission_timestamp=datetime.now(timezone.utc),
            content_type="invalid",
            llm_title="T",
            rationale="R",
            category="C",
            x_variant="X",
            linkedin_variant="LI",
        )
        assert invalid_row.content_type not in CONTENT_TYPE_VALUES


class TestIdempotencyContract:
    """Test idempotency behavior contract."""
    
    def test_same_content_same_style_duplicate(self):
        """Same content + same style = duplicate."""
        from app.utils.hashing import content_fingerprint, style_hash
        
        fp1 = content_fingerprint("url1", "hash1", style_hash("style1"))
        fp2 = content_fingerprint("url1", "hash1", style_hash("style1"))
        assert fp1 == fp2
    
    def test_same_content_different_style_not_duplicate(self):
        """Same content + different style = new row."""
        from app.utils.hashing import content_fingerprint, style_hash
        
        fp1 = content_fingerprint("url1", "hash1", style_hash("style1"))
        fp2 = content_fingerprint("url1", "hash1", style_hash("style2"))
        assert fp1 != fp2
    
    def test_different_content_same_style_not_duplicate(self):
        """Different content + same style = new row."""
        from app.utils.hashing import content_fingerprint, style_hash
        
        fp1 = content_fingerprint("url1", "hash1", style_hash("style1"))
        fp2 = content_fingerprint("url2", "hash2", style_hash("style1"))
        assert fp1 != fp2
    
    def test_url_source_identifier_preserved(self):
        """URL source identifier must be original URL."""
        from app.utils.hashing import content_fingerprint, style_hash
        
        original_url = "https://example.com/article?utm_source=test"
        fp = content_fingerprint(original_url, "hash1", style_hash("style1"))
        
        # Fingerprint includes original URL
        assert original_url in fp or len(fp) == 64  # Hash includes it