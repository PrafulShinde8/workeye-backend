import os
import sys
import argparse
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from db import fetch_all
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env'))

SCREENSHOT_SAVE_PATH = os.getenv('SCREENSHOT_SAVE_PATH', os.path.join(os.getcwd(), 'screenshots'))
SAVE_SCREENSHOTS_TO_FS = os.getenv('SAVE_SCREENSHOTS_TO_FS', 'true').lower() in ('1','true','yes')

parser = argparse.ArgumentParser(description='Backfill all screenshots from DB to filesystem')
parser.add_argument('--overwrite', action='store_true', help='Overwrite existing files')
parser.add_argument('--limit', type=int, default=0, help='Limit number of screenshots to export (0 = no limit)')
parser.add_argument('--company', type=int, help='Only export screenshots for this company id')
parser.add_argument('--member', type=int, help='Only export screenshots for this member id')
args = parser.parse_args()

if not SAVE_SCREENSHOTS_TO_FS:
    print('Saving to filesystem disabled via SAVE_SCREENSHOTS_TO_FS env variable. Set it to true to enable.')
    sys.exit(1)

os.makedirs(SCREENSHOT_SAVE_PATH, exist_ok=True)

query = 'SELECT id, company_id, member_id, screenshot_data, timestamp FROM screenshots WHERE screenshot_data IS NOT NULL'
params = []
if args.company:
    query += ' AND company_id = %s'
    params.append(args.company)
if args.member:
    query += ' AND member_id = %s'
    params.append(args.member)
query += ' ORDER BY id'
if args.limit and args.limit > 0:
    query += ' LIMIT %s'
    params.append(args.limit)

rows = fetch_all(query, tuple(params) if params else None)
if not rows:
    print('No screenshots to export with given filters')
    sys.exit(0)

written = 0
skipped = 0
errors = 0

for idx, r in enumerate(rows, start=1):
    sid = r['id']
    cid = r['company_id']
    mid = r['member_id']
    blob = r['screenshot_data']
    ts = r['timestamp']
    try:
        ts_str = ts.strftime('%Y%m%d_%H%M%S')
    except Exception:
        from datetime import datetime
        ts_str = datetime.utcnow().strftime('%Y%m%d_%H%M%S')

    file_dir = os.path.join(SCREENSHOT_SAVE_PATH, str(cid), str(mid))
    os.makedirs(file_dir, exist_ok=True)
    fname = f'screenshot_{sid}_{ts_str}.webp'
    fpath = os.path.join(file_dir, fname)

    if os.path.isfile(fpath) and not args.overwrite:
        skipped += 1
    else:
        try:
                with open(fpath, 'wb') as f:
                    f.write(blob)
                # Mark as saved in DB
                try:
                    from db import get_db
                    with get_db() as conn2:
                        cur2 = conn2.cursor()
                        cur2.execute("UPDATE screenshots SET is_saved_to_fs = TRUE, saved_filename = %s WHERE id = %s", (fpath, sid))
                except Exception as e:
                    print(f"⚠️ Failed to mark screenshot {sid} as saved: {e}")
                written += 1
            except Exception as e:
                print(f"⚠️ Failed to write {fpath}: {e}")
                errors += 1
    if idx % 50 == 0:
        print(f'Processed {idx}/{len(rows)} rows... written={written} skipped={skipped} errors={errors}')

print('Backfill complete')
print('Total rows:', len(rows))
print('Written:', written)
print('Skipped (existing):', skipped)
print('Errors:', errors)
print('Destination:', os.path.abspath(SCREENSHOT_SAVE_PATH))