import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from db import fetch_all

rows = fetch_all('''
SELECT id, member_id, company_id, file_size, width, height, timestamp
FROM screenshots
ORDER BY id DESC
LIMIT 10
''')

if not rows:
    print('No screenshots found')
else:
    for r in rows:
        print(r)
