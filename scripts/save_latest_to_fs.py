import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from db import fetch_all
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env'))

SCREENSHOT_SAVE_PATH = os.getenv('SCREENSHOT_SAVE_PATH', os.path.join(os.getcwd(), 'screenshots'))
SAVE_SCREENSHOTS_TO_FS = os.getenv('SAVE_SCREENSHOTS_TO_FS', 'true').lower() in ('1','true','yes')

rows = fetch_all('SELECT id, member_id, company_id, screenshot_data, timestamp FROM screenshots WHERE screenshot_data IS NOT NULL ORDER BY id DESC LIMIT 1')
if not rows:
    print('No screenshots found in database')
    sys.exit(0)

row = rows[0]
sid = row['id']
member_id = row['member_id']
company_id = row['company_id']
blob = row['screenshot_data']
if not blob:
    print('Latest screenshot blob is empty for id', sid)
    sys.exit(1)

print('SAVE_SCREENSHOTS_TO_FS=', SAVE_SCREENSHOTS_TO_FS)
print('SCREENSHOT_SAVE_PATH=', SCREENSHOT_SAVE_PATH)

if SAVE_SCREENSHOTS_TO_FS:
    file_dir = os.path.join(SCREENSHOT_SAVE_PATH, str(company_id), str(member_id))
    os.makedirs(file_dir, exist_ok=True)
    ts = row['timestamp']
    try:
        ts_str = ts.strftime('%Y%m%d_%H%M%S')
    except Exception:
        from datetime import datetime
        ts_str = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
    fname = f"screenshot_{sid}_{ts_str}.webp"
    fpath = os.path.join(file_dir, fname)
    with open(fpath, 'wb') as f:
        f.write(blob)
    print('Wrote file to', fpath)
else:
    print('Saving disabled by env')