"""Unit tests for LLM parser and schemas."""
import pytest

from app.llm.parser import (
    parse_llm_json,
    repair_x_post,
    validate_generation_result,
)
from app.llm.schemas import ContentGenerationResult, Variants
from app.utils.exceptions import LLMValidationError


class TestVariantsSchema:
    def test_valid_variants(self):
        v = Variants(x_post="Short post", linkedin_post="Longer professional post")
        assert v.x_post == "Short post"
        assert v.linkedin_post == "Longer professional post"
    
    def test_x_post_too_long(self):
        long_post = "x" * 281
        with pytest.raises(ValueError, match="280 characters"):
            Variants(x_post=long_post, linkedin_post="LinkedIn")
    
    def test_x_post_empty(self):
        with pytest.raises(ValueError, match="empty"):
            Variants(x_post="", linkedin_post="LinkedIn")
    
    def test_linkedin_empty(self):
        with pytest.raises(ValueError, match="empty"):
            Variants(x_post="X post", linkedin_post="")


class TestContentGenerationResultSchema:
    def test_valid_result(self):
        result = ContentGenerationResult(
            title="Test Title",
            rationale="Test rationale",
            category="Technology",
            variants=Variants(x_post="X post", linkedin_post="LinkedIn post"),
        )
        assert result.title == "Test Title"
    
    def test_empty_title_fails(self):
        with pytest.raises(ValueError):
            ContentGenerationResult(
                title="",
                rationale="Test",
                category="Tech",
                variants=Variants(x_post="X", linkedin_post="LI"),
            )
    
    def test_empty_category_fails(self):
        with pytest.raises(ValueError):
            ContentGenerationResult(
                title="Test",
                rationale="Test",
                category="",
                variants=Variants(x_post="X", linkedin_post="LI"),
            )


class TestParseLLMJSON:
    def test_direct_json(self):
        json_str = '{"title": "T", "rationale": "R", "category": "C", "variants": {"x_post": "X", "linkedin_post": "LI"}}'
        result = parse_llm_json(json_str)
        assert isinstance(result, ContentGenerationResult)
        assert result.title == "T"
    
    def test_markdown_fenced_json(self):
        json_str = '''```json
{"title": "T", "rationale": "R", "category": "C", "variants": {"x_post": "X", "linkedin_post": "LI"}}
```'''
        result = parse_llm_json(json_str)
        assert result.title == "T"
    
    def test_markdown_fenced_no_lang(self):
        json_str = '''```
{"title": "T", "rationale": "R", "category": "C", "variants": {"x_post": "X", "linkedin_post": "LI"}}
```'''
        result = parse_llm_json(json_str)
        assert result.title == "T"
    
    def test_json_embedded_in_text(self):
        text = '''Here is the result:
{"title": "T", "rationale": "R", "category": "C", "variants": {"x_post": "X", "linkedin_post": "LI"}}
Hope that helps!'''
        result = parse_llm_json(text)
        assert result.title == "T"
    
    def test_invalid_json_raises(self):
        with pytest.raises(LLMValidationError):
            parse_llm_json("not json at all")
    
    def test_incomplete_json_raises(self):
        with pytest.raises(LLMValidationError):
            parse_llm_json('{"title": "T"')


class TestValidateGenerationResult:
    def test_valid_result_no_errors(self):
        result = ContentGenerationResult(
            title="Title",
            rationale="Rationale",
            category="Category",
            variants=Variants(x_post="Short X", linkedin_post="Longer LinkedIn post"),
        )
        errors = validate_generation_result(result)
        assert errors == []
    
    def test_x_post_too_long_caught_at_construction(self):
        """Pydantic validation catches X post > 280 at construction."""
        with pytest.raises(ValueError, match="280"):
            ContentGenerationResult(
                title="T",
                rationale="R",
                category="C",
                variants=Variants(x_post="x" * 281, linkedin_post="LI"),
            )
    
    def test_empty_fields_caught_at_construction(self):
        """Pydantic validation catches empty fields at construction."""
        with pytest.raises(ValueError, match="empty"):
            ContentGenerationResult(
                title="",
                rationale="R",
                category="C",
                variants=Variants(x_post="X", linkedin_post="LI"),
            )
    
    def test_identical_variants(self):
        """Business validation catches identical variants (passes Pydantic)."""
        result = ContentGenerationResult(
            title="T",
            rationale="R",
            category="C",
            variants=Variants(x_post="Same", linkedin_post="Same"),
        )
        errors = validate_generation_result(result)
        assert any("identical" in e.lower() for e in errors)


class TestRepairXPost:
    def test_within_limit_unchanged(self):
        result = repair_x_post("Short post", "LinkedIn post")
        assert result == "Short post"
    
    def test_truncates_at_word_boundary(self):
        long_post = "This is a very long post that exceeds the character limit for X"
        result = repair_x_post(long_post, "LinkedIn", max_length=40)
        assert len(result) <= 40
        assert result.endswith("...")
    
    def test_hard_truncation_no_spaces(self):
        long_post = "Supercalifragilisticexpialidocious"
        result = repair_x_post(long_post, "LinkedIn", max_length=20)
        assert len(result) <= 20
        assert result.endswith("...")