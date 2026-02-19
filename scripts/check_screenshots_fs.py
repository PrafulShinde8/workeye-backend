import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from db import fetch_all
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env'))

SCREENSHOT_SAVE_PATH = os.getenv('SCREENSHOT_SAVE_PATH', os.path.join(os.getcwd(), 'screenshots'))
SAVE_SCREENSHOTS_TO_FS = os.getenv('SAVE_SCREENSHOTS_TO_FS', 'true').lower() in ('1','true','yes')

print('SAVE_SCREENSHOTS_TO_FS=', SAVE_SCREENSHOTS_TO_FS)
print('SCREENSHOT_SAVE_PATH=', SCREENSHOT_SAVE_PATH)

rows = fetch_all('SELECT id, company_id, member_id, file_size, timestamp FROM screenshots ORDER BY id')
if not rows:
    print('No screenshots found in DB')
    sys.exit(0)

total = len(rows)
with_data = fetch_all('SELECT COUNT(*) as c FROM screenshots WHERE screenshot_data IS NOT NULL')[0]['c']
print(f'Total screenshots rows: {total}')
print(f'Rows with screenshot binary data: {with_data}')

missing_files = []
for r in rows:
    sid = r['id']
    cid = r['company_id']
    mid = r['member_id']
    ts = r['timestamp']
    try:
        ts_str = ts.strftime('%Y%m%d_%H%M%S')
    except Exception:
        from datetime import datetime
        ts_str = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
    expected = os.path.join(SCREENSHOT_SAVE_PATH, str(cid), str(mid), f'screenshot_{sid}_{ts_str}.webp')
    if not os.path.isfile(expected):
        missing_files.append((sid, cid, mid, expected))

print(f'Files missing on disk: {len(missing_files)}')
if missing_files:
    print('Sample missing (first 20):')
    for tup in missing_files[:20]:
        print(tup)

# Also show files present on disk but not in DB
fs_files = []
for root, dirs, files in os.walk(SCREENSHOT_SAVE_PATH if os.path.isdir(SCREENSHOT_SAVE_PATH) else '.'):
    for f in files:
        if f.lower().endswith('.webp'):
            fs_files.append(os.path.join(root, f))

print(f'Files found on disk under {SCREENSHOT_SAVE_PATH}: {len(fs_files)}')

# Check if any DB row with data has no file and print an instruction for remediation
missing_with_data = len(missing_files) - (total - with_data)
print(f'Estimated screenshots with binary data missing files: {missing_with_data}')

print('\nDone')