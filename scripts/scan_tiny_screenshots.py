import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from db import fetch_all

OUT_DIR = os.path.join(os.path.dirname(__file__), 'exports')
os.makedirs(OUT_DIR, exist_ok=True)

# Criteria for 'tiny' or suspect screenshots
MIN_FILE_SIZE = 1024  # bytes
MIN_DIM = 100  # px

# Query rows that look suspect
rows = fetch_all("SELECT id, member_id, company_id, file_size, width, height, timestamp FROM screenshots ORDER BY id DESC LIMIT 500")
if not rows:
    print('No screenshots in DB')
    sys.exit(0)

suspect = []
for r in rows:
    fs = r.get('file_size') or 0
    w = r.get('width') or 0
    h = r.get('height') or 0
    if fs < MIN_FILE_SIZE or w < MIN_DIM or h < MIN_DIM:
        suspect.append(r)

print(f'Total scanned: {len(rows)}. Suspect small screenshots: {len(suspect)}')

# Export first 10 suspect screenshots (if any)
count = 0
for r in suspect[:10]:
    sid = r['id']
    row = fetch_all('SELECT screenshot_data FROM screenshots WHERE id = %s', (sid,))
    blob = row[0]['screenshot_data'] if row else None
    if not blob:
        print(f'No blob for id {sid}')
        continue
    # write file
    ts = r['timestamp']
    try:
        ts_str = ts.strftime('%Y%m%d_%H%M%S')
    except Exception:
        ts_str = 'unknown'
    fname = f'suspect_{sid}_{r["company_id"]}_{r["member_id"]}_{ts_str}.webp'
    outpath = os.path.join(OUT_DIR, fname)
    with open(outpath, 'wb') as f:
        f.write(blob)
    print('Exported', outpath, 'size', os.path.getsize(outpath), 'w,h=', r.get('width'), r.get('height'))
    count += 1

print('Done. Exported', count, 'sample suspect screenshots to', OUT_DIR)