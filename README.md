# ScannApp — Django OCR Backend Setup Guide

## What this does
Phone takes a photo → Django server runs OCR → result saved to Google Sheets.
No third-party OCR APIs. No per-scan costs. Runs on any Linux server or your PC.

---

## 1. Install system dependencies

### Ubuntu / Debian (server or WSL)
```bash
sudo apt update
sudo apt install -y python3 python3-pip python3-venv tesseract-ocr tesseract-ocr-eng
```

### Mac
```bash
brew install tesseract
```

### Windows
1. Download Tesseract installer: https://github.com/UB-Mannheim/tesseract/wiki
2. Install to `C:\Program Files\Tesseract-OCR\`
3. Set `TESSERACT_CMD=C:/Program Files/Tesseract-OCR/tesseract.exe` in your `.env`

---

## 2. Set up Python environment

```bash
cd scannapp
python3 -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

---

## 3. Set up Google Service Account (for Sheets access)

### A. Create a service account
1. Go to https://console.cloud.google.com
2. Create a new project (or use existing)
3. Enable **Google Sheets API**
4. Go to **IAM & Admin → Service Accounts → Create Service Account**
5. Name it `scannapp-sheets`
6. Click **Create** → skip optional steps → **Done**
7. Click the service account → **Keys** tab → **Add Key** → **Create new key** → **JSON**
8. Download the JSON file → rename it `service_account.json`
9. Place it in the `scannapp/` project root (same folder as `manage.py`)

### B. Share your Google Sheet with the service account
1. Open your Google Sheet
2. Click **Share**
3. Paste the service account email (looks like: `scannapp-sheets@your-project.iam.gserviceaccount.com`)
4. Set permission to **Editor**
5. Click **Send**

---

## 4. Configure environment

```bash
cp .env.example .env
```

Edit `.env`:
```
DJANGO_SECRET_KEY=any-long-random-string-here
GOOGLE_SHEET_ID=paste-your-sheet-id-here
GOOGLE_SERVICE_ACCOUNT_FILE=service_account.json
TESSERACT_CMD=/usr/bin/tesseract
```

**Finding your Sheet ID:**
`https://docs.google.com/spreadsheets/d/THIS_IS_YOUR_ID/edit`

---

## 5. Set up the Sheet headers (one time only)

```bash
source venv/bin/activate
python manage.py shell
```

In the shell:
```python
from scanner.sheets_service import setup_headers
setup_headers()
exit()
```

---

## 6. Run the server

```bash
source venv/bin/activate
python manage.py runserver 0.0.0.0:8000
```

Test it works:
```
http://localhost:8000/api/health/
```
You should see: `{"status": "ok", "service": "ScannApp"}`

---

## 7. Connect the frontend

In `templates/scanner/index.html`, line with `const BACKEND`:

**Local (PC on same WiFi as phone):**
```javascript
const BACKEND = 'http://192.168.x.x:8000';  // your PC's local IP
```

**Production server:**
```javascript
const BACKEND = 'https://your-server.com';
```

To find your PC's local IP:
- Linux/Mac: `ip addr show` or `ifconfig`
- Windows: `ipconfig` → look for IPv4 Address

---

## 8. Deploy to production (optional)

### Cheapest option: Railway.app (free tier available)
```bash
# Install Railway CLI
npm install -g @railway/cli
railway login
railway init
railway up
```

Set environment variables in Railway dashboard.

### Any Linux VPS (DigitalOcean, Hetzner, etc.)
```bash
# Using gunicorn + nginx
gunicorn scannapp.wsgi:application --bind 0.0.0.0:8000 --workers 2
```

---

## Project structure
```
scannapp/
├── manage.py
├── requirements.txt
├── .env.example
├── service_account.json        ← you add this (never commit to git)
├── scannapp/
│   ├── settings.py
│   ├── urls.py
│   └── wsgi.py
├── scanner/
│   ├── views.py                ← API endpoints
│   ├── ocr_service.py          ← image preprocessing + Tesseract
│   ├── sheets_service.py       ← Google Sheets writer
│   └── urls.py
└── templates/
    └── scanner/
        └── index.html          ← phone frontend
```

---

## API Reference

### POST /api/scan/
**With image (OCR):**
```
Content-Type: multipart/form-data
Body: image=<file>
```
Response:
```json
{ "success": true, "code": "c20250915364", "raw": "...", "saved": true }
```

**Manual entry (JSON):**
```
Content-Type: application/json
Body: { "code": "c20250915364" }
```

### GET /api/health/
```json
{ "status": "ok", "service": "ScannApp" }
```
