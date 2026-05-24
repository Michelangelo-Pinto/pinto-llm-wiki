"""Image preprocessing pipeline for improved Tesseract OCR accuracy.

Tesseract is sensitive to image quality. Preprocessing compensates for:
- Low contrast (adaptive thresholding)
- Slight rotation (deskew)
- Background noise (denoising)
- Blurry text (sharpening)

The default pipeline (grayscale -> deskew -> threshold) works well for
most scanned documents. Additional steps can be toggled via the 'steps'
parameter in ocr_preprocess_and_extract.
"""

import logging
from typing import List

import cv2
import numpy as np

logger = logging.getLogger(__name__)


def preprocess_for_ocr(image: np.ndarray, steps: List[str] = None) -> np.ndarray:
    """Apply a sequence of preprocessing steps to improve OCR accuracy.

    Args:
        image: Input image as a numpy array (BGR or grayscale).
        steps: List of preprocessing steps to apply. Default:
               ["grayscale", "deskew", "threshold"]
               Available: "grayscale", "deskew", "threshold", "denoise", "sharpen"

    Returns:
        Preprocessed image as a numpy array.
    """
    if steps is None:
        steps = ["grayscale", "deskew", "threshold"]

    for step in steps:
        if step == "grayscale":
            image = _to_grayscale(image)
        elif step == "deskew":
            image = _deskew(image)
        elif step == "threshold":
            image = _adaptive_threshold(image)
        elif step == "denoise":
            image = _denoise(image)
        elif step == "sharpen":
            image = _sharpen(image)

    return image


def _to_grayscale(image: np.ndarray) -> np.ndarray:
    """Convert to grayscale if the image has multiple channels."""
    if len(image.shape) == 3:
        return cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    return image


def _adaptive_threshold(image: np.ndarray) -> np.ndarray:
    """Apply adaptive Gaussian thresholding for uneven lighting.

    Uses block size 11 and constant 2, which works well for typical
    scanned documents at 300 DPI.
    """
    if len(image.shape) == 3:
        image = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    return cv2.adaptiveThreshold(
        image, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2
    )


def _deskew(image: np.ndarray) -> np.ndarray:
    """Correct slight rotation in scanned documents.

    Uses minAreaRect on non-white pixels to detect skew angle.
    Only corrects if the angle exceeds 0.5 degrees to avoid
    unnecessary rotation of straight documents.
    """
    if len(image.shape) == 3:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    else:
        gray = image

    # Find all non-white pixel coordinates (text pixels)
    coords = np.column_stack(np.where(gray < 200))
    if len(coords) == 0:
        return image

    angle = cv2.minAreaRect(coords)[-1]
    if angle < -45:
        angle = 90 + angle
    if abs(angle) < 0.5:
        return image  # Already straight enough

    (h, w) = image.shape[:2]
    center = (w // 2, h // 2)
    M = cv2.getRotationMatrix2D(center, angle, 1.0)
    return cv2.warpAffine(
        image, M, (w, h),
        flags=cv2.INTER_CUBIC,
        borderMode=cv2.BORDER_REPLICATE,
    )


def _denoise(image: np.ndarray) -> np.ndarray:
    """Remove background noise using fast non-local means denoising."""
    if len(image.shape) == 3:
        return cv2.fastNlMeansDenoisingColored(image, None, 10, 10, 7, 21)
    return cv2.fastNlMeansDenoising(image, None, 10, 7, 21)


def _sharpen(image: np.ndarray) -> np.ndarray:
    """Sharpen text edges using a Laplacian kernel."""
    kernel = np.array([[-1, -1, -1],
                       [-1,  9, -1],
                       [-1, -1, -1]])
    return cv2.filter2D(image, -1, kernel)
