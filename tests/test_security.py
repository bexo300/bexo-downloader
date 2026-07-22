"""
Bexo Downloader - Security Tests
"""

import pytest
from pathlib import Path

from bot.utils.security import SecurityManager


@pytest.fixture
def security():
    """Create security manager fixture."""
    return SecurityManager(max_file_size_mb=100)


def test_validate_url(security):
    """Test URL validation."""
    valid, error = security.validate_url("https://example.com/video")
    assert valid is True
    assert error is None
    
    valid, error = security.validate_url("../../../etc/passwd")
    assert valid is False


def test_sanitize_input(security):
    """Test input sanitization."""
    assert "\\x00" not in security.sanitize_input("hello\\x00world")
    assert len(security.sanitize_input("a" * 2000)) <= 1000


def test_generate_safe_filename(security):
    """Test safe filename generation."""
    assert ".." not in security.generate_safe_filename("../../../test.txt")
    assert "<" not in security.generate_safe_filename("test<file>.txt")
