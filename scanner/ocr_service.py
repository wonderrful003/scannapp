"""
ocr_service.py
Handles image preprocessing and text extraction using Tesseract.
Server-side OCR is dramatically more reliable than browser-side Tesseract.js
because we control the environment, can install system Tesseract with proper
trained data, and can apply OpenCV preprocessing properly.
"""
import re
import numpy as np
import cv2
import pytesseract
from PIL import Image
from django.conf import settings

pytesseract.pytesseract.tesseract_cmd = settings.TESSERACT_CMD


def extract_code(image_file) -> dict:
    """
    Main entry point. Takes a Django InMemoryUploadedFile or any file-like
    object. Returns:
        { 'success': True,  'code': 'c20250915364', 'raw': '...full OCR...' }
        { 'success': False, 'error': '...message...' }
    """
    try:
        # Load image via PIL then convert to OpenCV (numpy array)
        pil_img = Image.open(image_file).convert('RGB')
        img     = np.array(pil_img)
        img     = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)

        # Run two passes with different preprocessing and pick best result
        results = []
        for processed in [
            _preprocess_greyscale(img),
            _preprocess_adaptive(img),
            _preprocess_bottom_half(img),
        ]:
            text = _run_tesseract(processed)
            code = _pick_best_code(text)
            if code:
                results.append((code, text))

        if not results:
            return {'success': False, 'error': 'No readable text found in image'}

        # Return the best candidate (longest digit-heavy code wins)
        best_code, raw_text = max(results, key=lambda r: _score(r[0]))
        return {
            'success': True,
            'code'   : best_code,
            'raw'    : raw_text,
        }

    except Exception as e:
        return {'success': False, 'error': str(e)}


# ── Preprocessing strategies ──────────────────────────────────────────────────

def _preprocess_greyscale(img):
    """Greyscale + mild contrast boost. Gentlest option."""
    grey = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    # CLAHE = Contrast Limited Adaptive Histogram Equalization
    # Much better than a fixed threshold — adapts to local lighting
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    return clahe.apply(grey)


def _preprocess_adaptive(img):
    """Greyscale + adaptive threshold. Good for dark backgrounds."""
    grey = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    # Gaussian blur to reduce noise before thresholding
    blurred = cv2.GaussianBlur(grey, (3, 3), 0)
    # Adaptive threshold: each region uses its own local threshold
    # Much better than a fixed global cutoff (like the old gray > 128)
    return cv2.adaptiveThreshold(
        blurred, 255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY,
        blockSize=11, C=2
    )


def _preprocess_bottom_half(img):
    """
    Crops to the bottom 45% of the image (where text sits below barcode)
    then applies greyscale + CLAHE.
    Your label layout: barcode on top, serial number text on bottom.
    """
    h = img.shape[0]
    cropped = img[int(h * 0.55):, :]       # keep bottom 45%
    grey    = cv2.cvtColor(cropped, cv2.COLOR_BGR2GRAY)

    # Upscale 2× — tiny text reads much better at higher resolution
    upscaled = cv2.resize(grey, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)

    clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
    return clahe.apply(upscaled)


# ── Tesseract call ────────────────────────────────────────────────────────────

def _run_tesseract(processed_img) -> str:
    """Run Tesseract on a preprocessed (greyscale numpy) image."""
    # PSM 6  = assume a uniform block of text
    # PSM 7  = single text line
    # We try PSM 6 first (handles multi-line labels too)
    config = (
        '--psm 6 '
        '--oem 1 '                          # LSTM engine only
        '-c tessedit_char_whitelist='
        'abcdefghijklmnopqrstuvwxyz'
        'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
        '0123456789-_/'
    )
    pil = Image.fromarray(processed_img)
    return pytesseract.image_to_string(pil, config=config)


# ── Code extraction ───────────────────────────────────────────────────────────

def _pick_best_code(raw_text: str) -> str:
    """
    From raw OCR output, find the token most likely to be a serial number.
    Strategy: tokenise on whitespace, score each token by digit density.
    Your serials look like c20250915364 → 1 letter + 11 digits → ~92% digits.
    """
    if not raw_text:
        return ''

    # Split into tokens, strip non-alphanumeric chars from each
    tokens = [
        re.sub(r'[^a-zA-Z0-9]', '', t)
        for t in re.split(r'\s+', raw_text)
    ]
    tokens = [t for t in tokens if len(t) >= 4]

    if not tokens:
        # Fallback: regex match for letter-prefix + digits pattern
        m = re.search(r'[a-zA-Z]?\d{6,}', raw_text)
        return m.group(0) if m else ''

    # Pick highest-scoring token
    best = max(tokens, key=_score, default='')
    return best if _score(best) > 10 else ''


def _score(token: str) -> float:
    """Score a token by how much it looks like a serial number."""
    if not token:
        return 0
    digits  = sum(c.isdigit() for c in token)
    letters = sum(c.isalpha() for c in token)
    if digits < 3:
        return 0
    # High digit ratio + decent length = high score
    return (digits / len(token)) * 100 + min(len(token), 15)
