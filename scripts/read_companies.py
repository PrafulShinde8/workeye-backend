from db import fetch_all

rows = fetch_all('SELECT id, tracker_token, company_name FROM companies ORDER BY id')
for r in rows:
    print(f"id={r.get('id')}, name={r.get('company_name')}, token={r.get('tracker_token')}")
