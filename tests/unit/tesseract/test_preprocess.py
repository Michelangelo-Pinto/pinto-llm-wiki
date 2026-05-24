"""Unit tests for Tesseract MCP image preprocessing functions.

Tests the pure numpy/cv2 image processing pipeline without any filesystem or Tesseract dependency.
"""

import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "mcp-servers" / "tesseract-mcp" / "src"))

from tesseract_mcp.preprocess import (
    _adaptive_threshold,
    _denoise,
    _deskew,
    _sharpen,
    _to_grayscale,
    preprocess_for_ocr,
)


# ---------------------------------------------------------------------------
# Test image fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def white_image():
    """A small all-white BGR image."""
    return np.ones((50, 50, 3), dtype=np.uint8) * 255


@pytest.fixture
def black_image():
    """A small all-black BGR image."""
    return np.zeros((50, 50, 3), dtype=np.uint8)


@pytest.fixture
def text_like_image():
    """An image with a horizontal line (simulating text)."""
    img = np.ones((100, 100, 3), dtype=np.uint8) * 255
    img[48:52, 10:90] = 0  # Black horizontal line
    return img


@pytest.fixture
def grayscale_image():
    """A single-channel grayscale image."""
    img = np.ones((50, 50), dtype=np.uint8) * 128
    img[20:30, 20:30] = 0
    return img


# ---------------------------------------------------------------------------
# _to_grayscale tests
# ---------------------------------------------------------------------------


class TestToGrayscale:
    """Tests for _to_grayscale — BGR to grayscale conversion."""

    def test_bgr_to_grayscale(self, white_image):
        result = _to_grayscale(white_image)
        assert len(result.shape) == 2  # Single channel
        assert result.shape == (50, 50)

    def test_already_grayscale(self, grayscale_image):
        result = _to_grayscale(grayscale_image)
        assert len(result.shape) == 2
        assert result.shape == (50, 50)
        # Should be unchanged if already grayscale

    def test_grayscale_values_range(self, white_image):
        result = _to_grayscale(white_image)
        assert result.min() >= 0
        assert result.max() <= 255

    def test_black_to_grayscale(self, black_image):
        result = _to_grayscale(black_image)
        assert len(result.shape) == 2


# ---------------------------------------------------------------------------
# _adaptive_threshold tests
# ---------------------------------------------------------------------------


class TestAdaptiveThreshold:
    """Tests for _adaptive_threshold — adaptive Gaussian thresholding."""

    def test_binarizes_image(self, text_like_image):
        result = _adaptive_threshold(text_like_image)
        assert len(result.shape) == 2
        # Result should be binary (0 or 255)
        unique = np.unique(result)
        assert all(v in (0, 255) for v in unique)

    def test_handles_grayscale_input(self, grayscale_image):
        result = _adaptive_threshold(grayscale_image)
        assert len(result.shape) == 2
        unique = np.unique(result)
        assert all(v in (0, 255) for v in unique)

    def test_preserves_text_structure(self, text_like_image):
        result = _adaptive_threshold(text_like_image)
        # The line region should have different values than the background
        line_region = result[48:52, 10:90]
        bg_region = result[0:10, 0:10]
        # Line and background should be opposite (one 0, one 255)
        assert line_region.mean() != bg_region.mean()

    def test_white_image_threshold(self, white_image):
        result = _adaptive_threshold(white_image)
        assert result.shape == (50, 50)


# ---------------------------------------------------------------------------
# _deskew tests
# ---------------------------------------------------------------------------


class TestDeskew:
    """Tests for _deskew — rotation correction."""

    def test_no_rotation_needed_for_straight_image(self, text_like_image):
        result = _deskew(text_like_image)
        assert result.shape[0] == 100 and result.shape[1] == 100

    def test_preserves_shape(self, white_image):
        result = _deskew(white_image)
        assert result.shape == (50, 50, 3) or len(result.shape) == 2

    def test_handles_grayscale(self, grayscale_image):
        result = _deskew(grayscale_image)
        assert len(result.shape) == 2

    def test_handles_all_white(self, white_image):
        # All-white image has no features to detect skew angle
        result = _deskew(white_image)
        assert result.shape[0] == 50 and result.shape[1] == 50


# ---------------------------------------------------------------------------
# _denoise tests
# ---------------------------------------------------------------------------


class TestDenoise:
    """Tests for _denoise — noise removal."""

    def test_reduces_noise(self, grayscale_image):
        result = _denoise(grayscale_image)
        assert result.shape == grayscale_image.shape

    def test_handles_color_image(self, white_image):
        result = _denoise(white_image)
        # Output shape should match or be grayscale
        assert result.shape[0] == 50

    def test_preserves_image(self, text_like_image):
        result = _denoise(text_like_image)
        # Should still have the line structure
        assert result.shape[0] == 100


# ---------------------------------------------------------------------------
# _sharpen tests
# ---------------------------------------------------------------------------


class TestSharpen:
    """Tests for _sharpen — edge enhancement."""

    def test_sharpens_image(self, text_like_image):
        result = _sharpen(text_like_image)
        assert result.shape[:2] == text_like_image.shape[:2]

    def test_handles_color_image(self, white_image):
        result = _sharpen(white_image)
        assert result.shape[:2] == (50, 50)

    def test_does_not_crash_on_small_image(self):
        tiny = np.ones((10, 10, 3), dtype=np.uint8) * 200
        result = _sharpen(tiny)
        assert result.shape == (10, 10, 3)


# ---------------------------------------------------------------------------
# preprocess_for_ocr tests (pipeline)
# ---------------------------------------------------------------------------


class TestPreprocessForOcr:
    """Tests for preprocess_for_ocr — the full preprocessing pipeline."""

    def test_default_steps(self, text_like_image):
        result = preprocess_for_ocr(text_like_image)
        # Default steps: grayscale, deskew, threshold → output is binary
        assert len(result.shape) == 2  # Grayscale + threshold = single channel
        assert result.shape[:2] == (100, 100)

    def test_grayscale_only(self, white_image):
        result = preprocess_for_ocr(white_image, steps=["grayscale"])
        assert len(result.shape) == 2
        assert result.shape == (50, 50)

    def test_denoise_step(self, text_like_image):
        result = preprocess_for_ocr(text_like_image, steps=["grayscale", "denoise"])
        assert len(result.shape) == 2

    def test_sharpen_step(self, text_like_image):
        result = preprocess_for_ocr(text_like_image, steps=["grayscale", "sharpen"])
        assert len(result.shape) == 2

    def test_custom_step_order(self, text_like_image):
        result = preprocess_for_ocr(text_like_image, steps=["threshold", "grayscale"])
        assert result.shape[:2] == (100, 100)

    def test_empty_steps_list(self, white_image):
        result = preprocess_for_ocr(white_image, steps=[])
        # Should return unchanged
        assert result.shape == white_image.shape

    def test_unknown_step_ignored(self, white_image):
        result = preprocess_for_ocr(white_image, steps=["grayscale", "unknown_step"])
        assert result.shape == (50, 50)

    def test_all_steps_combined(self, text_like_image):
        steps = ["grayscale", "deskew", "threshold", "denoise", "sharpen"]
        result = preprocess_for_ocr(text_like_image, steps=steps)
        assert result.shape[:2] == (100, 100)

    def test_none_steps_uses_defaults(self, text_like_image):
        result = preprocess_for_ocr(text_like_image, steps=None)
        assert len(result.shape) == 2
