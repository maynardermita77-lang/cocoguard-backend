import sqlite3

conn = sqlite3.connect('cocoguard.db')
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

# Get column names
cursor.execute("PRAGMA table_info(scans)")
cols = cursor.fetchall()
print("=== Scans table columns ===")
for c in cols:
    print(f"  {c['name']} ({c['type']})")

print("\n=== Scans from ID 21 onwards ===")
cursor.execute("""
    SELECT s.id, s.user_id, s.pest_type_id, s.confidence, s.notes,
           s.image_url, s.created_at, s.location_text, s.status, s.source,
           pt.name as pest_name
    FROM scans s
    LEFT JOIN pest_types pt ON s.pest_type_id = pt.id
    WHERE s.id >= 21
    ORDER BY s.id ASC
""")
rows = cursor.fetchall()
for r in rows:
    pest = r['pest_name'] or r['notes'] or 'None'
    conf = r['confidence'] or 0
    loc = (r['location_text'] or 'N/A')[:40]
    status = r['status'] or 'N/A'
    source = r['source'] or 'N/A'
    print(f"ID:{r['id']:>3} | User:{r['user_id'] or 'N/A':>4} | {pest:<30} | {conf:>6.1f}% | {status:<10} | {source:<8} | {r['created_at'] or 'N/A'} | {loc}")

print(f"\nTotal: {len(rows)} scans from ID 21+")
conn.close()
