import re
import base64
import requests
import os
from PIL import Image
import io
import json

VISION_KEY = os.getenv('VISION_API_KEY', '')
VISION_URL = 'https://vision.googleapis.com/v1/images:annotate'


def extract_code(image_file) -> dict:
    """
    Send image to Google Cloud Vision API and extract serial number.
    Fixed endpoint and better serial number extraction.
    """
    try:
        # Read and encode image to base64
        img_bytes = image_file.read()

        # Resize if too large — Vision API has a 10MB limit
        pil_img = Image.open(io.BytesIO(img_bytes)).convert('RGB')

        # Resize to max 1600px wide for faster processing
        max_w = 1600
        if pil_img.width > max_w:
            ratio = max_w / pil_img.width
            new_h = int(pil_img.height * ratio)
            pil_img = pil_img.resize((max_w, new_h), Image.LANCZOS)

        # Increase contrast for better text detection
        from PIL import ImageEnhance
        enhancer = ImageEnhance.Contrast(pil_img)
        pil_img = enhancer.enhance(1.5)

        # Convert back to bytes
        buffer = io.BytesIO()
        pil_img.save(buffer, format='JPEG', quality=95)
        img_b64 = base64.b64encode(buffer.getvalue()).decode('utf-8')

        # Call Vision API - FIXED: using correct API key parameter
        payload = {
            'requests': [{
                'image': {'content': img_b64},
                'features': [
                    {'type': 'TEXT_DETECTION', 'maxResults': 10},
                ],
                'imageContext': {
                    'languageHints': ['en']  # Hint for English text
                }
            }]
        }

        response = requests.post(
            f'{VISION_URL}?key={VISION_KEY}',
            json=payload,
            timeout=15
        )
        
        # Check if request was successful
        if response.status_code != 200:
            return {'success': False, 'error': f'API error: {response.status_code}'}
            
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

        # Extract serial number - improved pattern matching
        code = _extract_serial(full_text, annotations)

        if not code:
            return {'success': False, 'error': 'Could not extract valid serial number'}

        return {
            'success': True,
            'code': code,
            'raw': full_text,
        }

    except requests.Timeout:
        return {'success': False, 'error': 'Vision API timeout — try again'}
    except Exception as e:
        return {'success': False, 'error': str(e)}


def _extract_serial(full_text: str, annotations: list) -> str:
    """
    Extract the serial number from Vision API results.
    Your codes look like: c20250915364 (letter followed by digits)
    """
    # Clean the text
    full_text = full_text.replace('\n', ' ').strip()
    
    # Strategy 1: Look for pattern: optional letter + 6+ digits
    # This matches patterns like "c20250915364" or "20250915364"
    pattern = r'[a-zA-Z]?\d{6,}'
    matches = re.findall(pattern, full_text)
    
    if matches:
        # Return the longest match (most likely the serial)
        return max(matches, key=len)
    
    # Strategy 2: Look for letter followed by numbers (like "c2025")
    pattern2 = r'[a-zA-Z]\d{4,}'
    matches = re.findall(pattern2, full_text)
    if matches:
        return max(matches, key=len)
    
    # Strategy 3: Get all words and score them
    words = full_text.split()
    scored_words = []
    
    for word in words:
        # Clean word of special characters
        clean_word = re.sub(r'[^a-zA-Z0-9]', '', word)
        if len(clean_word) < 4:
            continue
            
        # Calculate score based on digit density and length
        digits = sum(c.isdigit() for c in clean_word)
        letters = sum(c.isalpha() for c in clean_word)
        
        if digits >= 4:  # At least 4 digits
            score = digits * 2 + len(clean_word)
            scored_words.append((score, clean_word))
    
    if scored_words:
        # Return highest scoring word
        scored_words.sort(reverse=True)
        return scored_words[0][1]
    
    # Last resort: return first reasonable looking text
    words = [w for w in words if len(w) >= 4]
    if words:
        return words[0]
    
    return full_text[:30]  # Truncate if nothing else