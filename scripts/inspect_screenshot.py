import os
from PIL import Image
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from db import fetch_all

# Change this id if you want to inspect a different screenshot
screenshot_id = 251

# File path expected
# Try to find DB row first
row = fetch_all('SELECT id, member_id, company_id, file_size, width, height, timestamp FROM screenshots WHERE id = %s', (screenshot_id,))
if not row:
    print('No DB row for screenshot id', screenshot_id)
    sys.exit(1)
row = row[0]
print('DB row:', row)

# Construct expected path
cid = row['company_id']
mid = row['member_id']
try:
    ts = row['timestamp']
    ts_str = ts.strftime('%Y%m%d_%H%M%S')
except Exception:
    ts_str = 'unknown'

base = os.getenv('SCREENSHOT_SAVE_PATH', './screenshots')
path = os.path.join(base, str(cid), str(mid), f'screenshot_{screenshot_id}_{ts_str}.webp')
print('Expected path:', path)

if os.path.isfile(path):
    print('File exists. Size bytes:', os.path.getsize(path))
    try:
        img = Image.open(path)
        print('Format:', img.format)
        print('Dimensions (w,h):', img.size)
        print('Mode:', img.mode)
        img.load()
        print('Image loaded OK')
    except Exception as e:
        print('Error loading image with PIL:', e)
else:
    print('File not found at expected path')

# Fallback: list files in the company/member folder
folder = os.path.join(base, str(cid), str(mid))
if os.path.isdir(folder):
    print('\nFiles in folder:')
    for f in os.listdir(folder):
        p = os.path.join(folder, f)
        print(f, os.path.getsize(p))
else:
    print('Folder not found:', folder)
