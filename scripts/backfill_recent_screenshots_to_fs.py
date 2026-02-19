"""
Backfill recent screenshots to filesystem (safe, limited to recent days)
Usage:
    python scripts/backfill_recent_screenshots_to_fs.py --days 7 --limit 500

This script only backfills screenshots where `screenshot_data` exists and `is_saved_to_fs` is false.
It defaults to the last 7 days to avoid huge operations. It will write files using the same
path format used by the tracker upload handler and update the DB fields.
"""

import os
import argparse
from datetime import datetime, timedelta
from db import get_db

SCREENSHOT_SAVE_PATH = os.getenv('SCREENSHOT_SAVE_PATH', os.path.join(os.getcwd(), 'screenshots'))


def write_file(path, data):
    try:
        dirn = os.path.dirname(path)
        os.makedirs(dirn, exist_ok=True)
        with open(path, 'wb') as f:
            f.write(data)
        return True
    except Exception as e:
        print(f"⚠️ Failed to write file {path}: {e}")
        return False


def backfill(days=7, limit=500):
    cutoff = datetime.utcnow() - timedelta(days=days)
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT id, company_id, member_id, timestamp, screenshot_data
            FROM screenshots
            WHERE screenshot_data IS NOT NULL AND (is_saved_to_fs IS DISTINCT FROM TRUE OR saved_filename IS NULL)
              AND timestamp >= %s
            ORDER BY timestamp ASC
            LIMIT %s
        """, (cutoff, limit))
        rows = cur.fetchall()

        print(f"Found {len(rows)} screenshots to backfill (cutoff={cutoff.isoformat()})")

        success = 0
        skipped = 0
        for r in rows:
            sid = r['id']
            cid = r['company_id']
            mid = r['member_id']
            ts = r['timestamp']
            data = r['screenshot_data']
            ts_str = None
            try:
                ts_str = ts.strftime('%Y%m%d_%H%M%S')
            except Exception:
                ts_str = datetime.utcnow().strftime('%Y%m%d_%H%M%S')

            fname = f"screenshot_{sid}_{ts_str}.webp"
            fpath = os.path.join(SCREENSHOT_SAVE_PATH, str(cid), str(mid), fname)

            if os.path.exists(fpath):
                print(f"✅ Already exists on disk: {fpath}")
                try:
                    cur.execute("UPDATE screenshots SET is_saved_to_fs = TRUE, saved_filename = %s WHERE id = %s", (fpath, sid))
                    conn.commit()
                except Exception as e:
                    print(f"⚠️ Failed to update DB for existing file {sid}: {e}")
                skipped += 1
                continue

            ok = write_file(fpath, data)
            if ok:
                try:
                    cur.execute("UPDATE screenshots SET is_saved_to_fs = TRUE, saved_filename = %s WHERE id = %s", (fpath, sid))
                    conn.commit()
                    print(f"✅ Wrote and marked: {fpath}")
                    success += 1
                except Exception as e:
                    print(f"⚠️ Wrote file but failed DB update for {sid}: {e}")
            else:
                print(f"❌ Failed to write: {fpath}")

        print(f"Backfill complete: wrote={success}, skipped={skipped}, attempted={len(rows)}")


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--days', type=int, default=7, help='How many days back to scan')
    parser.add_argument('--limit', type=int, default=500, help='Max number of screenshots to process')
    args = parser.parse_args()
    backfill(days=args.days, limit=args.limit)
