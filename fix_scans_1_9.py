import sqlite3
conn = sqlite3.connect('cocoguard.db')
c = conn.cursor()

# Scan 1: White Grub 68.22% (4/4 TTA agreement)
c.execute("""
    UPDATE scans 
    SET pest_type_id = 7, 
        confidence = 68.22, 
        notes = 'Detected: White Grub (68.22%, TTA 4/4) [corrected from false Out-of-Scope]'
    WHERE id = 1
""")
print(f"Scan 1 updated: {c.rowcount} row(s)")

# Scan 9: APW Larvae 68.1% (3/4 TTA agreement)
c.execute("""
    UPDATE scans 
    SET pest_type_id = 2, 
        confidence = 68.1, 
        notes = 'Detected: APW Larvae (68.1%, TTA 3/4) [corrected from false Out-of-Scope]'
    WHERE id = 9
""")
print(f"Scan 9 updated: {c.rowcount} row(s)")

conn.commit()

# Verify
for sid in [1, 9]:
    c.execute('SELECT id, pest_type_id, confidence, notes FROM scans WHERE id=?', (sid,))
    row = c.fetchone()
    print(f'Verified Scan {sid}: pest_type_id={row[1]}, confidence={row[2]}, notes={row[3]}')

conn.close()
print("Done!")
