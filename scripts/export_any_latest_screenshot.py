import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from db import fetch_all

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

out_dir = os.path.join(os.path.dirname(__file__), 'exports')
os.makedirs(out_dir, exist_ok=True)
filename = os.path.join(out_dir, f'screenshot_{sid}_member{member_id}_company{company_id}.webp')
with open(filename, 'wb') as f:
    f.write(blob)

print('Exported screenshot:', filename)