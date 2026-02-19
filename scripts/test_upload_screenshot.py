import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from db import fetch_all
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env'))

import base64
import json
try:
    import requests
except Exception:
    requests = None

# Find a company with tracker_token
# Try to find a company with a stored tracker_token if possible
companies = fetch_all("SELECT id, tracker_token FROM companies WHERE tracker_token IS NOT NULL AND tracker_token != '' LIMIT 1")
if companies:
    company = companies[0]
    company_id = company['id']
    tracker_token = company['tracker_token']
    print('Using company with stored tracker_token:', company_id)
else:
    # fallback: pick any active company and craft a base64 token of the form '<company_id>:x'
    any_company = fetch_all('SELECT id FROM companies WHERE is_active = TRUE LIMIT 1')
    if not any_company:
        print('No active company found')
        sys.exit(1)
    company_id = any_company[0]['id']
    import base64 as _b64
    tracker_token = _b64.b64encode(f"{company_id}:test".encode()).decode()
    print('Using company (fallback):', company_id, 'with generated token')

# Find a member with a registered device for this company
row = fetch_all('''
SELECT m.id as member_id, m.email, d.device_id
FROM members m
JOIN devices d ON d.member_id = m.id
WHERE m.company_id = %s
LIMIT 1
''', (company_id,))
if not row:
    # Try globally
    row = fetch_all('''
    SELECT m.id as member_id, m.email, d.device_id, m.company_id
    FROM members m
    JOIN devices d ON d.member_id = m.id
    LIMIT 1
    ''')
    if not row:
        print('No member+device combo found in DB')
        sys.exit(1)
    row = row[0]
    member_id = row['member_id']
    email = row['email']
    device_id = row['device_id']
    company_id = row.get('company_id', company_id)
    print('Using global member/device:', member_id, email, device_id, 'company', company_id)
else:
    row = row[0]
    member_id = row['member_id']
    email = row['email']
    device_id = row['device_id']
    print('Using member:', member_id, email)
    print('Using device_id:', device_id)

# Create a tiny 2x2 black PNG
try:
    from PIL import Image
    from io import BytesIO
    img = Image.new('RGB', (2,2), color=(0,0,0))
    buf = BytesIO()
    img.save(buf, format='PNG')
    b = buf.getvalue()
    b64 = base64.b64encode(b).decode()
    data_url = 'data:image/png;base64,' + b64
except Exception as e:
    print('PIL not available:', e)
    # fallback to known tiny png base64
    data_url = 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAIAAAACCAQAAADZc7J/AAAADElEQVQImWNgYGBgAAAABQABDQottAAAAABJRU5ErkJggg=='

payload = {
    'email': email,
    'deviceid': device_id,
    'screenshot': data_url
}

url = os.getenv('BACKEND_URL', 'http://localhost:10000') + '/tracker/upload'
print('Posting to', url)
print('X-Tracker-Token header:', tracker_token if tracker_token else '<none>')

if requests is None:
    print('requests not installed, aborting HTTP test')
    sys.exit(1)

resp = requests.post(url, json=payload, headers={'X-Tracker-Token': tracker_token}, timeout=10)
print('Status:', resp.status_code)
try:
    print('Response JSON:', resp.json())
except Exception:
    print('Response text:', resp.text)

# Check filesystem
SAVE_SCREENSHOTS_TO_FS = os.getenv('SAVE_SCREENSHOTS_TO_FS', 'true').lower() in ('1','true','yes')
SCREENSHOT_SAVE_PATH = os.getenv('SCREENSHOT_SAVE_PATH', os.path.join(os.getcwd(), 'screenshots'))
print('SAVE_SCREENSHOTS_TO_FS=', SAVE_SCREENSHOTS_TO_FS)
print('SCREENSHOT_SAVE_PATH=', SCREENSHOT_SAVE_PATH)

# If response contains screenshotid, check file
try:
    data = resp.json()
    sid = data.get('screenshotid')
except Exception:
    sid = None

if sid and SAVE_SCREENSHOTS_TO_FS:
    # find file in expected folder
    import glob
    pattern = os.path.join(SCREENSHOT_SAVE_PATH, str(company_id), str(member_id), f'screenshot_{sid}_*.webp')
    matches = glob.glob(pattern)
    print('Filesystem matches for screenshot id:', matches)
else:
    print('No screenshot id in response or saving disabled')
