import re
import numpy as np
import cv2
import pytesseract
from PIL import Image
from django.conf import settings
import shutil

# Find tesseract automatically
cmd = getattr(settings, 'TESSERACT_CMD', None) or shutil.which('tesseract') or '/usr/bin/tesseract'
pytesseract.pytesseract.tesseract_cmd = cmd


def extract_code(image_file) -> dict:
    try:
        pil_img = Image.open(image_file).convert('RGB')
        img     = np.array(pil_img)
        img     = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)

        candidates = []

        # Pass 1 — original image, no processing at all
        text = _run_tesseract_pil(pil_img)
        code = _pick_best_code(text)
        if code:
            candidates.append((code, text))

        # Pass 2 — greyscale only, no binarising
        grey = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        text = _run_tesseract_cv(grey)
        code = _pick_best_code(text)
        if code:
            candidates.append((code, text))

        # Pass 3 — crop bottom 50%, upscale 2x, greyscale
        h = img.shape[0]
        cropped = img[int(h * 0.50):, :]
        grey2   = cv2.cvtColor(cropped, cv2.COLOR_BGR2GRAY)
        large   = cv2.resize(grey2, None, fx=2, fy=2,
                             interpolation=cv2.INTER_CUBIC)
        text = _run_tesseract_cv(large)
        code = _pick_best_code(text)
        if code:
            candidates.append((code, text))

        # Pass 4 — CLAHE contrast enhancement
        grey3 = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        enhanced = clahe.apply(grey3)
        text = _run_tesseract_cv(enhanced)
        code = _pick_best_code(text)
        if code:
            candidates.append((code, text))

        # Pass 5 — adaptive threshold (gentler than hard binarise)
        grey4   = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(grey4, (3, 3), 0)
        thresh  = cv2.adaptiveThreshold(
            blurred, 255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY,
            blockSize=15, C=4
        )
        text = _run_tesseract_cv(thresh)
        code = _pick_best_code(text)
        if code:
            candidates.append((code, text))

        if not candidates:
            # Last resort — return ALL raw text so user can see what
            # Tesseract actually read and edit it manually
            raw = _run_tesseract_pil(pil_img)
            return {
                'success': True,
                'code'   : raw.strip()[:50],
                'raw'    : raw,
            }

        best_code, raw_text = max(candidates, key=lambda r: _score(r[0]))
        return {
            'success': True,
            'code'   : best_code,
            'raw'    : raw_text,
        }

    except Exception as e:
        return {'success': False, 'error': str(e)}


def _run_tesseract_pil(pil_img) -> str:
    """Run Tesseract directly on a PIL image — no preprocessing."""
    configs = [
        '--psm 6 --oem 1',   # uniform block of text
        '--psm 7 --oem 1',   # single line
        '--psm 11 --oem 1',  # sparse text — finds text anywhere
        '--psm 3 --oem 1',   # fully automatic
    ]
    results = []
    for cfg in configs:
        try:
            text = pytesseract.image_to_string(pil_img, config=cfg)
            results.append(text)
        except Exception:
            pass
    return '\n'.join(results)


def _run_tesseract_cv(cv_img) -> str:
    """Run Tesseract on an OpenCV (numpy) greyscale image."""
    pil = Image.fromarray(cv_img)
    return _run_tesseract_pil(pil)


def _pick_best_code(raw_text: str) -> str:
    """
    Extract the most likely serial number from raw OCR text.
    Tries multiple strategies and returns the best match.
    """
    if not raw_text or not raw_text.strip():
        return ''

    # Strategy 1 — exact pattern match: optional letter + 6+ digits
    # Matches: c20250915364, 20250915364, C12345678
    matches = re.findall(r'[a-zA-Z]?\d{6,}', raw_text)
    if matches:
        return max(matches, key=len)

    # Strategy 2 — score all tokens by digit density
    tokens = [
        re.sub(r'[^a-zA-Z0-9]', '', t)
        for t in re.split(r'\s+', raw_text)
    ]
    tokens = [t for t in tokens if len(t) >= 4]

    if tokens:
        best = max(tokens, key=_score, default='')
        if _score(best) > 20:
            return best

    return ''


def _score(token: str) -> float:
    if not token:
        return 0
    digits  = sum(c.isdigit() for c in token)
    if digits < 3:
        return 0
    return (digits / len(token)) * 100 + min(len(token), 15)