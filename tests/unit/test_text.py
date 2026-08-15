"""Unit tests for text utilities."""
from app.utils.text import (
    count_characters,
    ensure_max_length,
    extract_urls,
    is_empty_content,
    normalize_whitespace,
    sanitize_filename,
    truncate_text,
)


class TestNormalizeWhitespace:
    def test_collapses_spaces(self):
        assert normalize_whitespace("hello    world") == "hello world"
    
    def test_collapses_tabs(self):
        assert normalize_whitespace("hello\t\tworld") == "hello world"
    
    def test_collapses_newlines(self):
        assert normalize_whitespace("hello\n\n\nworld") == "hello\n\nworld"
    
    def test_preserves_paragraphs(self):
        text = "para1\n\npara2\n\n\npara3"
        result = normalize_whitespace(text)
        assert result == "para1\n\npara2\n\npara3"
    
    def test_strips_whitespace(self):
        assert normalize_whitespace("  hello  ") == "hello"


class TestTruncateText:
    def test_no_truncation_needed(self):
        assert truncate_text("short", 100) == "short"
    
    def test_truncates_with_suffix(self):
        result = truncate_text("hello world", 8)
        assert result == "hello..."
        assert len(result) <= 8
    
    def test_custom_suffix(self):
        result = truncate_text("hello world", 8, suffix=">>")
        assert result.endswith(">>")


class TestIsEmptyContent:
    def test_empty_string(self):
        assert is_empty_content("") is True
    
    def test_whitespace_only(self):
        assert is_empty_content("   \n\t  ") is True
    
    def test_non_empty(self):
        assert is_empty_content("hello") is False


class TestSanitizeFilename:
    def test_removes_path(self):
        assert sanitize_filename("path/to/file.pdf") == "file.pdf"
        assert sanitize_filename("path\\to\\file.pdf") == "file.pdf"
    
    def test_removes_special_chars(self):
        assert sanitize_filename("file@#$%.pdf") == "file.pdf"
    
    def test_limits_length(self):
        long_name = "a" * 300 + ".pdf"
        result = sanitize_filename(long_name)
        assert len(result) <= 255


class TestExtractURLs:
    def test_extracts_single_url(self):
        urls = extract_urls("Check out https://example.com")
        assert urls == ["https://example.com"]
    
    def test_extracts_multiple_urls(self):
        text = "See https://a.com and http://b.com"
        urls = extract_urls(text)
        assert len(urls) == 2
    
    def test_no_urls(self):
        assert extract_urls("hello world") == []


class TestCountCharacters:
    def test_counts_correctly(self):
        assert count_characters("hello") == 5
        assert count_characters("") == 0
        assert count_characters("🎉") == 1  # Unicode


class TestEnsureMaxLength:
    def test_within_limit(self):
        assert ensure_max_length("short", 10) == "short"
    
    def test_truncates_at_word_boundary(self):
        text = "This is a long sentence that should be truncated"
        result = ensure_max_length(text, 20)
        assert len(result) <= 20
        assert result.endswith("...")
    
    def test_hard_truncation_if_no_space(self):
        text = "Supercalifragilisticexpialidocious"
        result = ensure_max_length(text, 15)
        assert len(result) <= 15
        assert result.endswith("...")