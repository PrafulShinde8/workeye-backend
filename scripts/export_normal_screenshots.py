import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from db import fetch_all

OUT_DIR = os.path.join(os.path.dirname(__file__), 'exports')
os.makedirs(OUT_DIR, exist_ok=True)

# Export a few recent normal-sized screenshots
rows = fetch_all("SELECT id, member_id, company_id, file_size, width, height, timestamp FROM screenshots WHERE file_size > 1024 AND width > 200 AND height > 200 ORDER BY id DESC LIMIT 5")
if not rows:
    print('No normal screenshots found')
    sys.exit(0)

for r in rows:
    sid = r['id']
    row = fetch_all('SELECT screenshot_data FROM screenshots WHERE id = %s', (sid,))
    blob = row[0]['screenshot_data'] if row else None
    if not blob:
        print(f'No blob for id {sid}')
        continue
    ts = r['timestamp']
    try:
        ts_str = ts.strftime('%Y%m%d_%H%M%S')
    except Exception:
        ts_str = 'unknown'
    fname = f'normal_{sid}_{r["company_id"]}_{r["member_id"]}_{ts_str}.webp'
    outpath = os.path.join(OUT_DIR, fname)
    with open(outpath, 'wb') as f:
        f.write(blob)
    print('Exported', outpath, 'size', os.path.getsize(outpath), 'w,h=', r.get('width'), r.get('height'))

print('Done')