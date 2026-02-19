import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from db import fetch_all
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env'))

import base64
import requests

# Find member with is_punched_in = true and a device
row = fetch_all('''
SELECT m.id as member_id, m.email, d.device_id, m.company_id
FROM members m
JOIN devices d ON d.member_id = m.id
WHERE m.is_punched_in = TRUE
LIMIT 1
''')

if not row:
    print('No punched-in member found')
    sys.exit(1)

row = row[0]
member_id = row['member_id']
email = row['email']
device_id = row['device_id']
company_id = row['company_id']
print('Using member:', member_id, email, 'device:', device_id, 'company:', company_id)

# Use company's tracker token
company = fetch_all('SELECT tracker_token FROM companies WHERE id = %s', (company_id,))[0]
tracker_token = company.get('tracker_token')
if not tracker_token:
    import base64 as _b64
    tracker_token = _b64.b64encode(f"{company_id}:test".encode()).decode()

# Create a larger realistic screenshot for testing (1280x720)
from PIL import Image
from io import BytesIO
img = Image.new('RGB', (1280,720), color=(100,120,140))
buf = BytesIO()
img.save(buf, format='PNG')
b = buf.getvalue()
b64 = base64.b64encode(b).decode()
data_url = 'data:image/png;base64,' + b64

payload = {
    'email': email,
    'deviceid': device_id,
    'screenshot': data_url
}

# Force local backend for this test (port 10001)
import os
url = os.getenv('BACKEND_URL', 'http://127.0.0.1:10001') + '/tracker/upload'
print('Posting to', url)
resp = requests.post(url, json=payload, headers={'X-Tracker-Token': tracker_token}, timeout=10)
print('Status:', resp.status_code)
print('Response:', resp.json())

sid = resp.json().get('screenshotid')
print('screenshot id:', sid)

# check filesystem
save_path = os.getenv('SCREENSHOT_SAVE_PATH', './screenshots')
pattern = os.path.join(save_path, str(company_id), str(member_id), f'screenshot_{sid}_*.webp')
import glob
matches = glob.glob(pattern)
print('Filesystem matches:', matches)