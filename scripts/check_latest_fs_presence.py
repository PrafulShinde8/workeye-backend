import os, sys, glob
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from db import fetch_all
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env'))
SCREENSHOT_SAVE_PATH = os.getenv('SCREENSHOT_SAVE_PATH', os.path.join(os.getcwd(), 'screenshots'))

rows = fetch_all('SELECT id, member_id, company_id FROM screenshots ORDER BY id DESC LIMIT 10')
for r in rows:
    sid = r['id']
    cid = r['company_id']
    mid = r['member_id']
    pattern = os.path.join(SCREENSHOT_SAVE_PATH, str(cid), str(mid), f'screenshot_{sid}_*.webp')
    matches = glob.glob(pattern)
    print(sid, '->', 'FOUND' if matches else 'MISSING', matches[:3])
