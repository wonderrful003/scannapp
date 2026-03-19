import re
import base64
import requests
import os
from PIL import Image
import io

VISION_KEY = os.getenv('VISION_API_KEY', '')
VISION_URL = 'https://vision.googleapis.com/v1/images:annotate'


def extract_code(image_file) -> dict:
    """
    Send image to Google Cloud Vision API and extract serial number.
    Much more accurate than Tesseract for real-world photos.
    """
    try:
        # Read and encode image to base64
        img_bytes = image_file.read()

        # Resize if too large — Vision API has a 10MB limit
        pil_img = Image.open(io.BytesIO(img_bytes)).convert('RGB')

        # Resize to max 1600px wide for faster processing
        max_w = 1600
        if pil_img.width > max_w:
            ratio  = max_w / pil_img.width
            new_h  = int(pil_img.height * ratio)
            pil_img = pil_img.resize((max_w, new_h), Image.LANCZOS)

        # Convert back to bytes
        buffer = io.BytesIO()
        pil_img.save(buffer, format='JPEG', quality=90)
        img_b64 = base64.b64encode(buffer.getvalue()).decode('utf-8')

        # Call Vision API
        payload = {
            'requests': [{
                'image'   : {'content': img_b64},
                'features': [
                    {'type': 'TEXT_DETECTION',          'maxResults': 50},
                    {'type': 'DOCUMENT_TEXT_DETECTION', 'maxResults': 1},
                ]
            }]
        }

        response = requests.post(
            f'{VISION_URL}?key={VISION_KEY}',
            json=payload,
            timeout=10
        )
        data = response.json()

        # Check for API errors
        if 'error' in data:
            return {'success': False, 'error': data['error']['message']}

        resp = data.get('responses', [{}])[0]

        if 'error' in resp:
            return {'success': False, 'error': resp['error']['message']}

        annotations = resp.get('textAnnotations', [])
        if not annotations:
            return {'success': False, 'error': 'No text found in image'}

        full_text = annotations[0].get('description', '')

        # Extract serial number
        code = _extract_serial(full_text, annotations)

        return {
            'success': True,
            'code'   : code,
            'raw'    : full_text,
        }

    except requests.Timeout:
        return {'success': False, 'error': 'Vision API timeout — try again'}
    except Exception as e:
        return {'success': False, 'error': str(e)}


def _extract_serial(full_text: str, annotations: list) -> str:
    """
    Extract the serial number from Vision API results.
    Your codes look like: c20250915364
    """
    # Strategy 1 — match exact pattern: optional letter + 6+ digits
    matches = re.findall(r'[a-zA-Z]?\d{6,}', full_text)
    if matches:
        return max(matches, key=len)

    # Strategy 2 — score each word by digit density
    words = [
        a.get('description', '').strip()
        for a in annotations[1:]  # skip index 0 = full text
    ]
    words = [re.sub(r'[^a-zA-Z0-9]', '', w) for w in words]
    words = [w for w in words if len(w) >= 4]

    if words:
        best = max(words, key=_score, default='')
        if _score(best) > 20:
            return best

    # Last resort — return cleaned full text
    return full_text.replace('\n', ' ').strip()[:50]


def _score(token: str) -> float:
    if not token:
        return 0
    digits = sum(c.isdigit() for c in token)
    if digits < 3:
        return 0
    return (digits / len(token)) * 100 + min(len(token), 15)