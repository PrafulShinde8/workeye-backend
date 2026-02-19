import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from db import get_db

with get_db() as conn:
    cur = conn.cursor()
    cur.execute("UPDATE screenshots SET is_valid = FALSE, invalid_reason = 'too_small_or_small_dimensions' WHERE (file_size IS NOT NULL AND file_size < 1024) OR (width IS NOT NULL AND width < 100) OR (height IS NOT NULL AND height < 100)")
    print('Rows updated (marked invalid):', cur.rowcount)

    # Mark valid for others
    cur.execute("UPDATE screenshots SET is_valid = TRUE, invalid_reason = NULL WHERE NOT ((file_size IS NOT NULL AND file_size < 1024) OR (width IS NOT NULL AND width < 100) OR (height IS NOT NULL AND height < 100))")
    print('Rows updated (marked valid):', cur.rowcount)
