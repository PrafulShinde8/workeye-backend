import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from db import fetch_all

member_id = 38
rows = fetch_all(
    'SELECT id, screenshot_data, timestamp FROM screenshots WHERE member_id = %s ORDER BY id DESC LIMIT 1',
    (member_id,)
)
if not rows:
    print('No screenshots found for member', member_id)
    sys.exit(0)

row = rows[0]
sid = row['id']
blob = row['screenshot_data']
if not blob:
    print('Screenshot data is empty for id', sid)
    sys.exit(1)

out_dir = os.path.join(os.path.dirname(__file__), 'exports')
os.makedirs(out_dir, exist_ok=True)
filename = os.path.join(out_dir, f'screenshot_{sid}.webp')
with open(filename, 'wb') as f:
    f.write(blob)

print('Exported screenshot:', filename)
