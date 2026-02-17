"""
Fix scans where pest_type_id is set but notes indicate Out-of-Scope.
Also check for scans that were DETECTED when they shouldn't have been
(e.g., suspicious class spread).
"""
import sqlite3

conn = sqlite3.connect('cocoguard.db')
cursor = conn.cursor()

# 1. Fix scans where notes say Out-of-Scope but pest_type_id is not NULL
print("=== Fixing Out-of-Scope scans with non-null pest_type_id ===")
cursor.execute("""
    SELECT id, pest_type_id, notes FROM scans 
    WHERE notes LIKE '%Out-of-Scope%' AND pest_type_id IS NOT NULL
""")
rows = cursor.fetchall()
for row in rows:
    print(f"  Scan {row[0]}: pest_type_id={row[1]}, notes={row[2]} -> Setting pest_type_id=NULL")
    cursor.execute("UPDATE scans SET pest_type_id = NULL WHERE id = ?", (row[0],))

if not rows:
    print("  (None found)")

# 2. Show all current scans for review
print("\n=== All scans (latest 20) ===")
cursor.execute("""
    SELECT s.id, s.pest_type_id, pt.name as pest_name, s.confidence, s.notes 
    FROM scans s 
    LEFT JOIN pest_types pt ON s.pest_type_id = pt.id
    ORDER BY s.id DESC LIMIT 20
""")
for row in cursor.fetchall():
    status = "✅ DETECTED" if row[1] else "❌ OUT_OF_SCOPE"
    print(f"  Scan {row[0]}: {status} | pest_type_id={row[1]} ({row[2]}) | conf={row[3]} | notes={row[4][:60] if row[4] else 'N/A'}...")

conn.commit()
conn.close()
print("\nDone!")
