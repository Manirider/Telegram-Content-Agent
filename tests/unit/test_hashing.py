"""Unit tests for hashing utilities."""
from app.utils.hashing import (
    content_fingerprint,
    normalize_url_for_hash,
    sha256_bytes,
    sha256_hash,
    style_hash,
)


class TestSHA256Hash:
    def test_hash_string(self):
        result = sha256_hash("hello world")
        assert len(result) == 64
        assert result == sha256_hash("hello world")  # Deterministic
    
    def test_hash_bytes(self):
        result = sha256_bytes(b"hello world")
        assert len(result) == 64
        assert result == sha256_bytes(b"hello world")
    
    def test_different_inputs_different_hashes(self):
        assert sha256_hash("a") != sha256_hash("b")


class TestContentFingerprint:
    def test_fingerprint_combines_all_parts(self):
        fp1 = content_fingerprint("source1", "hash1", "style1")
        fp2 = content_fingerprint("source1", "hash1", "style2")
        fp3 = content_fingerprint("source2", "hash1", "style1")
        
        assert fp1 != fp2  # Different style
        assert fp1 != fp3  # Different source
        assert len(fp1) == 64
    
    def test_fingerprint_deterministic(self):
        fp1 = content_fingerprint("src", "hash", "style")
        fp2 = content_fingerprint("src", "hash", "style")
        assert fp1 == fp2


class TestStyleHash:
    def test_empty_style(self):
        assert style_hash(None) == "no-style"
        assert style_hash("") == "no-style"
        assert style_hash("   ") == "no-style"
    
    def test_non_empty_style(self):
        h1 = style_hash("witty tone")
        h2 = style_hash("witty tone")
        assert h1 == h2
        assert len(h1) == 64
        assert h1 != "no-style"
    
    def test_different_styles_different_hashes(self):
        assert style_hash("style1") != style_hash("style2")


class TestNormalizeURLForHash:
    def test_normalizes_scheme_and_host(self):
        url = "HTTPS://Example.COM/path"
        normalized = normalize_url_for_hash(url)
        assert normalized == "https://example.com/path"
    
    def test_removes_fragment(self):
        url = "https://example.com/path#section"
        normalized = normalize_url_for_hash(url)
        assert "#" not in normalized
    
    def test_sorts_query_params(self):
        url = "https://example.com/path?b=2&a=1"
        normalized = normalize_url_for_hash(url)
        assert "a=1&b=2" in normalized
    
    def test_removes_default_ports(self):
        assert normalize_url_for_hash("http://example.com:80/path") == "http://example.com/path"
        assert normalize_url_for_hash("https://example.com:443/path") == "https://example.com/path"
        assert normalize_url_for_hash("http://example.com:8080/path") == "http://example.com:8080/path"
    
    def test_root_path_normalized(self):
        assert normalize_url_for_hash("https://example.com/") == "https://example.com"