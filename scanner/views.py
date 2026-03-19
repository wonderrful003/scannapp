"""
views.py
Two endpoints:
  GET  /           → serves the frontend HTML
  POST /api/scan/  → receives image, runs OCR, writes to Sheets
  GET  /api/health/→ health check
"""
import json
from django.http import JsonResponse
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.shortcuts import render

from .ocr_service import extract_code
from .sheets_service import append_scan


def index(request):
    """Serve the frontend."""
    return render(request, 'scanner/index.html')


def health(request):
    """Health check — useful for deployment monitoring."""
    return JsonResponse({'status': 'ok', 'service': 'ScannApp'})


@method_decorator(csrf_exempt, name='dispatch')
class ScanView(View):
    """
    POST /api/scan/
    Accepts multipart/form-data with an 'image' file field.
    OR JSON body with { "code": "manual-entry-code" } for manual saves.

    Response:
      200 { "success": true,  "code": "c20250915364", "saved": true }
      400 { "success": false, "error": "..." }
      500 { "success": false, "error": "..." }
    """

    def post(self, request):
        # ── Manual entry (JSON body, no image) ───────────────────────────────
        content_type = request.content_type or ''
        if 'application/json' in content_type:
            try:
                body = json.loads(request.body)
                code = (body.get('code') or '').strip()
                if not code:
                    return JsonResponse(
                        {'success': False, 'error': 'code field is empty'},
                        status=400
                    )
                result = append_scan(code, raw_text='manual entry')
                return JsonResponse({
                    'success': True,
                    'code': code,
                    'saved': result['success'],
                    'sheet_error': result.get('error'),
                })
            except json.JSONDecodeError:
                return JsonResponse(
                    {'success': False, 'error': 'Invalid JSON'},
                    status=400
                )

        # ── Image upload → OCR → Sheets ───────────────────────────────────────
        image_file = request.FILES.get('image')
        if not image_file:
            return JsonResponse(
                {'success': False, 'error': 'No image file in request'},
                status=400
            )

        # Validate it's an image
        allowed = {'image/jpeg', 'image/png', 'image/webp', 'image/gif'}
        if image_file.content_type not in allowed:
            return JsonResponse(
                {'success': False, 'error': f'Unsupported file type: {image_file.content_type}'},
                status=400
            )

        # File size limit: 10MB
        if image_file.size > 10 * 1024 * 1024:
            return JsonResponse(
                {'success': False, 'error': 'Image too large (max 10MB)'},
                status=400
            )

        # Run OCR
        ocr_result = extract_code(image_file)
        if not ocr_result['success']:
            return JsonResponse(
                {'success': False, 'error': ocr_result['error']},
                status=422
            )

        code = ocr_result['code']
        raw_text = ocr_result.get('raw', '')

        # Write to Google Sheets
        sheet_result = append_scan(code, raw_text)

        return JsonResponse({
            'success': True,
            'code': code,
            'raw': raw_text[:100],  # Truncate for response
            'saved': sheet_result['success'],
            'sheet_error': sheet_result.get('error'),
        })