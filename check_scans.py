import sqlite3

conn = sqlite3.connect('cocoguard.db')
cursor = conn.cursor()

# Find scans where notes say Out-of-Scope but pest_type_id is not null
print("=== Scans with Out-of-Scope notes but non-null pest_type_id ===")
cursor.execute("""
    SELECT id, pest_type_id, confidence, notes 
    FROM scans 
    WHERE notes LIKE '%Out-of-Scope%' AND pest_type_id IS NOT NULL
""")
rows = cursor.fetchall()
for row in rows:
    print(row)

if not rows:
    print("(None found - data is consistent)")

print("\n=== All scans (latest 15) ===")
cursor.execute("""
    SELECT id, pest_type_id, confidence, notes 
    FROM scans 
    ORDER BY id DESC 
    LIMIT 15
""")
for row in cursor.fetchall():
    print(row)

conn.close()
