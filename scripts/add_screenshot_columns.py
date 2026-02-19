import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from db import get_db

with get_db() as conn:
    cur = conn.cursor()
    # Check and add columns
    cols = ['is_valid', 'invalid_reason', 'is_saved_to_fs', 'saved_filename']
    existing = []
    cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name = 'screenshots'")
    existing = [r['column_name'] for r in cur.fetchall()]

    if 'is_valid' not in existing:
        cur.execute("ALTER TABLE screenshots ADD COLUMN is_valid BOOLEAN DEFAULT TRUE")
        print('Added is_valid')
    else:
        print('is_valid exists')

    if 'invalid_reason' not in existing:
        cur.execute("ALTER TABLE screenshots ADD COLUMN invalid_reason TEXT NULL")
        print('Added invalid_reason')
    else:
        print('invalid_reason exists')

    if 'is_saved_to_fs' not in existing:
        cur.execute("ALTER TABLE screenshots ADD COLUMN is_saved_to_fs BOOLEAN DEFAULT FALSE")
        print('Added is_saved_to_fs')
    else:
        print('is_saved_to_fs exists')

    if 'saved_filename' not in existing:
        cur.execute("ALTER TABLE screenshots ADD COLUMN saved_filename TEXT NULL")
        print('Added saved_filename')
    else:
        print('saved_filename exists')

print('Migration complete')