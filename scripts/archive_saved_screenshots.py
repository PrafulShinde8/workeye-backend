"""
Archive (undo) filesystem screenshot saves for a time range or member(s).
Usage examples:
  # Dry-run for last 7 days:
  python scripts/archive_saved_screenshots.py --days 7 --dry-run

  # Archive specific member (moves files to ARCHIVE_SCREENSHOT_PATH)
  python scripts/archive_saved_screenshots.py --member 42

This helps undo the filesystem mirroring step by moving files and clearing DB flags.
"""

import os
import argparse
from datetime import datetime, timedelta
from shutil import move
from db import get_db

SCREENSHOT_SAVE_PATH = os.getenv('SCREENSHOT_SAVE_PATH', os.path.join(os.getcwd(), 'screenshots'))
ARCHIVE_PATH = os.getenv('ARCHIVE_SCREENSHOT_PATH', os.path.join(os.getcwd(), 'screenshots_archive'))


def archive_file(src, dest):
    try:
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        move(src, dest)
        return True
    except Exception as e:
        print(f"⚠️ Failed to move {src} -> {dest}: {e}")
        return False


def archive(days=7, member_id=None, dry_run=True):
    cutoff = datetime.utcnow() - timedelta(days=days)
    with get_db() as conn:
        cur = conn.cursor()
        query = "SELECT id, saved_filename FROM screenshots WHERE is_saved_to_fs = TRUE"
        params = []
        if member_id:
            query += " AND member_id = %s"
            params.append(member_id)
        else:
            query += " AND timestamp >= %s"
            params.append(cutoff)

        cur.execute(query, tuple(params))
        rows = cur.fetchall()

        print(f"Found {len(rows)} saved screenshots eligible for archive (dry_run={dry_run})")
        archived = 0
        for r in rows:
            sid = r['id']
            saved = r['saved_filename']
            if not saved or not os.path.exists(saved):
                print(f"⚠️ File missing on disk for screenshot {sid}: {saved}")
                # Still clear DB flags if file absent on disk
                try:
                    cur.execute("UPDATE screenshots SET is_saved_to_fs = FALSE, saved_filename = NULL WHERE id = %s", (sid,))
                    conn.commit()
                except Exception as e:
                    print(f"⚠️ Failed to clear DB flags for {sid}: {e}")
                continue
            # Destination path mirrors company/member structure under ARCHIVE_PATH
            # Attempt to keep filename
            rel = os.path.relpath(saved, SCREENSHOT_SAVE_PATH)
            dest = os.path.join(ARCHIVE_PATH, rel)

            print(f"Would archive: {saved} -> {dest}")
            if not dry_run:
                ok = archive_file(saved, dest)
                if ok:
                    try:
                        cur.execute("UPDATE screenshots SET is_saved_to_fs = FALSE, saved_filename = NULL WHERE id = %s", (sid,))
                        conn.commit()
                        archived += 1
                    except Exception as e:
                        print(f"⚠️ Failed to update DB for archived {sid}: {e}")
        print(f"Archive complete: archived={archived}, total_checked={len(rows)}")


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--days', type=int, default=7, help='How many days back to scan')
    parser.add_argument('--member', type=int, help='Specific member id to archive')
    parser.add_argument('--dry-run', action='store_true', default=False, help='Do not move files, just show what would happen')
    args = parser.parse_args()
    archive(days=args.days, member_id=args.member, dry_run=args.dry_run)
