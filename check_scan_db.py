import sqlite3
conn = sqlite3.connect('cocoguard.db')
c = conn.cursor()

# Check current state of scans 1 and 9
for sid in [1, 9]:
    c.execute('SELECT id, pest_type_id, confidence, notes FROM scans WHERE id=?', (sid,))
    row = c.fetchone()
    if row:
        print(f'Scan {sid}: pest_type_id={row[1]}, confidence={row[2]}, notes={row[3]}')
    else:
        print(f'Scan {sid}: NOT FOUND')

# Get pest_type IDs
c.execute("SELECT id, name FROM pest_types WHERE name IN ('White Grub', 'APW Larvae')")
for row in c.fetchall():
    print(f'PestType: {row[1]} -> id={row[0]}')

conn.close()
