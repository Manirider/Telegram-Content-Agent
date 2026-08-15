"""Unit tests for URL utilities."""
import pytest

from app.utils.exceptions import IngestionError
from app.utils.urls import (
    is_safe_url,
    is_valid_http_url,
    normalize_url,
    validate_url,
)


class TestIsValidHTTPURL:
    def test_valid_http(self):
        assert is_valid_http_url("http://example.com") is True
    
    def test_valid_https(self):
        assert is_valid_http_url("https://example.com") is True
    
    def test_valid_with_path(self):
        assert is_valid_http_url("https://example.com/path/to/page") is True
    
    def test_valid_with_query(self):
        assert is_valid_http_url("https://example.com?query=value") is True
    
    def test_invalid_ftp(self):
        assert is_valid_http_url("ftp://example.com") is False
    
    def test_invalid_no_scheme(self):
        assert is_valid_http_url("example.com") is False
    
    def test_invalid_empty(self):
        assert is_valid_http_url("") is False
    
    def test_invalid_no_netloc(self):
        assert is_valid_http_url("http://") is False


class TestValidateURL:
    def test_valid_url_passes(self):
        result = validate_url("https://example.com")
        assert result == "https://example.com"
    
    def test_strips_whitespace(self):
        result = validate_url("  https://example.com  ")
        assert result == "https://example.com"
    
    def test_empty_raises(self):
        with pytest.raises(IngestionError):
            validate_url("")
    
    def test_invalid_scheme_raises(self):
        with pytest.raises(IngestionError):
            validate_url("ftp://example.com")
    
    def test_malformed_raises(self):
        with pytest.raises(IngestionError):
            validate_url("not a url")


class TestNormalizeURL:
    def test_lowercases_scheme_and_host(self):
        result = normalize_url("HTTPS://EXAMPLE.COM/Path")
        assert result == "https://example.com/Path"
    
    def test_removes_default_ports(self):
        assert normalize_url("http://example.com:80/path") == "http://example.com/path"
        assert normalize_url("https://example.com:443/path") == "https://example.com/path"
        assert normalize_url("http://example.com:8080/path") == "http://example.com:8080/path"
    
    def test_preserves_path_and_query(self):
        url = "https://example.com/path?query=value#fragment"
        result = normalize_url(url)
        assert result == "https://example.com/path?query=value#fragment"


class TestIsSafeURL:
    def test_allows_public_domains(self):
        assert is_safe_url("https://example.com") is True
        assert is_safe_url("https://google.com") is True
        assert is_safe_url("https://github.com") is True
    
    def test_blocks_localhost(self):
        assert is_safe_url("http://localhost") is False
        assert is_safe_url("http://127.0.0.1") is False
        assert is_safe_url("http://[::1]") is False
        assert is_safe_url("http://0.0.0.0") is False
    
    def test_blocks_private_ips(self):
        assert is_safe_url("http://192.168.1.1") is False
        assert is_safe_url("http://10.0.0.1") is False
        assert is_safe_url("http://172.16.0.1") is False
    
    def test_blocks_local_domains(self):
        assert is_safe_url("http://myserver.local") is False
        assert is_safe_url("http://internal.internal") is False
    
    def test_allows_public_ips(self):
        assert is_safe_url("https://8.8.8.8") is True
        assert is_safe_url("https://1.1.1.1") is True