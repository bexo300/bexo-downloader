"""
Bexo Downloader - Helper Tests
"""

import pytest

from bot.utils.helpers import (
    extract_platform,
    format_duration,
    format_number,
    format_size,
    generate_progress_bar,
    get_platform_icon,
    is_valid_url,
    sanitize_filename,
)


def test_generate_progress_bar():
    """Test progress bar generation."""
    bar = generate_progress_bar(50)
    assert "50.0%" in bar
    assert "█" in bar
    assert "░" in bar


def test_format_size():
    """Test size formatting."""
    assert format_size(1024) == "1.0 KiB"
    assert format_size(1024 * 1024) == "1.0 MiB"


def test_format_duration():
    """Test duration formatting."""
    result = format_duration(3661)
    assert "hour" in result or "ساعة" in result


def test_sanitize_filename():
    """Test filename sanitization."""
    assert sanitize_filename("test<file>.txt") == "test_file_.txt"
    assert len(sanitize_filename("a" * 300)) < 210


def test_extract_platform():
    """Test platform extraction."""
    assert extract_platform("https://tiktok.com/video/123") == "tiktok"
    assert extract_platform("https://instagram.com/p/123") == "instagram"
    assert extract_platform("https://youtube.com/watch?v=123") == "youtube"
    assert extract_platform("https://unknown.com") is None


def test_is_valid_url():
    """Test URL validation."""
    assert is_valid_url("https://example.com") is True
    assert is_valid_url("not-a-url") is False


def test_get_platform_icon():
    """Test platform icons."""
    assert get_platform_icon("tiktok") == "🎵"
    assert get_platform_icon("youtube") == "▶️"
    assert get_platform_icon("unknown") == "🔗"


def test_format_number():
    """Test number formatting."""
    assert "1,000" in format_number(1000)
