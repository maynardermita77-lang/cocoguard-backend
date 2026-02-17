import sqlite3

conn = sqlite3.connect('cocoguard.db')
conn.row_factory = sqlite3.Row
cursor = conn.cursor()
cursor.execute('SELECT id, image_url, notes FROM scans WHERE id >= 21 ORDER BY id')
for r in cursor.fetchall():
    img = r['image_url'] or 'None'
    notes = (r['notes'] or '')[:100]
    sid = r['id']
    print(f"ID:{sid:>3} | Image: {img}")
    print(f"      Notes: {notes}")
    print()
conn.close()
