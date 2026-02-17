import sqlite3
conn = sqlite3.connect('cocoguard.db')
c = conn.cursor()

# Check pest_types table
print("=== PEST TYPES TABLE ===")
c.execute('SELECT id, name FROM pest_types ORDER BY id')
for r in c.fetchall():
    print(f"  ID {r[0]}: {r[1]}")

# Find detected scans grouped by pest type
print("\n=== DETECTED SCANS BY PEST TYPE ===")
c.execute("""SELECT s.image_url, pt.name, s.confidence, s.notes 
             FROM scans s LEFT JOIN pest_types pt ON s.pest_type_id = pt.id 
             WHERE s.pest_type_id IS NOT NULL 
             ORDER BY pt.name, s.confidence DESC""")
rows = c.fetchall()
if rows:
    for r in rows:
        name = r[1] or "?"
        conf = r[2] or 0
        print(f"  {name:<22} | {conf:>5.1f}% | {r[0]}")
else:
    print("  (No detected scans found - table was truncated)")

# Check total scans
c.execute('SELECT COUNT(*) FROM scans')
print(f"\n  Total scans in DB: {c.fetchone()[0]}")

conn.close()
