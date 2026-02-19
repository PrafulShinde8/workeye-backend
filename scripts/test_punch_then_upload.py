"""
Test: Punch in then immediately upload screenshot to exercise the grace window logic
Usage: python scripts/test_punch_then_upload.py
"""

import os
import sys
import time
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from db import fetch_all
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env'))

import base64
import requests
from PIL import Image
from io import BytesIO

# Find a member not punched in (if none, pick any member and ensure they are punched out first)
row = fetch_all('''
SELECT m.id as member_id, m.email, d.device_id, m.company_id
FROM members m
JOIN devices d ON d.member_id = m.id
WHERE m.is_punched_in = FALSE
LIMIT 1
''')

if not row:
    # fallback: pick any member
    print('No unpunched-in member found; picking any member and ensuring it is punched out first')
    row = fetch_all('''
    SELECT m.id as member_id, m.email, d.device_id, m.company_id
    FROM members m
    JOIN devices d ON d.member_id = m.id
    LIMIT 1
    ''')
    if not row:
        print('No members found in DB to test')
        sys.exit(1)
    row = row[0]
    # attempt to punch out (best-effort) to ensure clean state
    try:
        # Force local backend for cleanup step
        BACKEND = 'http://127.0.0.1:10001'
        requests.post(BACKEND + '/api/attendance/punch-out', json={'member_email': row['email'], 'company_id': row['company_id']}, timeout=5)
        print('Attempted punch-out for cleanup (using local backend)')
    except Exception:
        pass
else:
    row = row[0]
member_id = row['member_id']
email = row['email']
device_id = row['device_id']
company_id = row['company_id']
print('Using member:', member_id, email, 'device:', device_id, 'company:', company_id)

company = fetch_all('SELECT tracker_token FROM companies WHERE id = %s', (company_id,))[0]
tracker_token = company.get('tracker_token')
if not tracker_token:
    import base64 as _b64
    tracker_token = _b64.b64encode(f"{company_id}:test".encode()).decode()

# Force local backend for test to avoid hitting remote Render instance
BACKEND = 'http://127.0.0.1:10001'  # override BACKEND_URL env for safe local testing
print('Using backend:', BACKEND)

# Create a sample screenshot
img = Image.new('RGB', (1280,720), color=(80,100,140))
buf = BytesIO()
img.save(buf, format='PNG')
b = buf.getvalue()
b64 = base64.b64encode(b).decode()
data_url = 'data:image/png;base64,' + b64

print('1) Punching in via API...')
res1 = requests.post(BACKEND + '/api/attendance/punch-in', json={'member_email': email, 'company_id': company_id}, timeout=10)
print('Punch-in status:', res1.status_code, res1.text)

print('2) Immediately uploading screenshot (no delay)...')
payload = {'email': email, 'deviceid': device_id, 'screenshot': data_url}
resp = requests.post(BACKEND + '/tracker/upload', json=payload, headers={'X-Tracker-Token': tracker_token}, timeout=10)
print('Upload status:', resp.status_code, resp.text)

print('3) Upload after 2 seconds delay...')
# optional extra upload to ensure subsequent saves
time.sleep(2)
resp2 = requests.post(BACKEND + '/tracker/upload', json=payload, headers={'X-Tracker-Token': tracker_token}, timeout=10)
print('Upload2 status:', resp2.status_code, resp2.text)

# Check filesystem
save_path = os.getenv('SCREENSHOT_SAVE_PATH', './screenshots')
import glob
pattern = os.path.join(save_path, str(company_id), str(member_id), 'screenshot_*.webp')
matches = glob.glob(pattern)
print('Filesystem matches:', matches)

# Cleanup: punch out to restore state
print('4) Punching out')
res_out = requests.post(BACKEND + '/api/attendance/punch-out', json={'member_email': email, 'company_id': company_id}, timeout=10)
print('Punch-out status:', res_out.status_code, res_out.text)
