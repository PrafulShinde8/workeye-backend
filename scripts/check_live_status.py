import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from db import get_db, get_ist_now, IST

with get_db() as conn:
    cur = conn.cursor()
    cur.execute("SELECT id, name, is_punched_in, last_activity_at, last_heartbeat_at FROM members WHERE is_active = TRUE ORDER BY id")
    rows = cur.fetchall()

now = get_ist_now()

print('Now (IST):', now.isoformat())
for r in rows:
    lid = r['last_activity_at']
    lhb = r['last_heartbeat_at']
    latest = lid or lhb
    derived = 'offline'
    if r['is_punched_in']:
        if latest:
            if latest.tzinfo is None:
                import pytz
                latest = pytz.UTC.localize(latest)
            latest_ist = latest.astimezone(IST)
            diff = (now - latest_ist).total_seconds()
            if diff <= 120:
                derived = 'active'
            elif diff <= 600:
                derived = 'idle'
            else:
                derived = 'offline'
        else:
            derived = 'active'
    else:
        derived = 'offline'
    print(f"{r['id']:3} {r['name'][:20]:20} punched_in={r['is_punched_in']:5} last_activity={str(lid)[:19]:19} last_heartbeat={str(lhb)[:19]:19} -> {derived}")
