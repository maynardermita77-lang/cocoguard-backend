"""Truncate all scans, history, notifications and delete uploaded images."""
import sqlite3
import os
import shutil

DB_PATH = "cocoguard.db"

conn = sqlite3.connect(DB_PATH)
c = conn.cursor()

# List all tables
c.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = [r[0] for r in c.fetchall()]
print(f"All tables: {tables}")

# Show counts for scan-related tables
for t in tables:
    c.execute(f'SELECT COUNT(*) FROM [{t}]')
    print(f"  {t}: {c.fetchone()[0]} rows")

print("\n--- TRUNCATING ---")

# Truncate scans
c.execute("DELETE FROM scans")
print(f"Deleted all rows from scans")

# Truncate notifications if exists
if 'notifications' in tables:
    c.execute("DELETE FROM notifications")
    print(f"Deleted all rows from notifications")

# Truncate feedback if exists
if 'feedback' in tables:
    c.execute("DELETE FROM feedback")
    print(f"Deleted all rows from feedback")

# Reset auto-increment sequences
c.execute("DELETE FROM sqlite_sequence WHERE name IN ('scans', 'notifications', 'feedback')")
print("Reset auto-increment sequences")

conn.commit()

# Verify
c.execute("SELECT COUNT(*) FROM scans")
print(f"\nScans remaining: {c.fetchone()[0]}")
conn.close()

# Delete uploaded images
upload_base = "uploads"
folders_to_clean = ["scans", "unknown_pest_reports"]

for folder in folders_to_clean:
    folder_path = os.path.join(upload_base, folder)
    if os.path.exists(folder_path):
        count = len([f for f in os.listdir(folder_path) if os.path.isfile(os.path.join(folder_path, f))])
        # Remove all files
        for f in os.listdir(folder_path):
            fp = os.path.join(folder_path, f)
            if os.path.isfile(fp):
                os.remove(fp)
        print(f"Deleted {count} files from {folder_path}/")
    else:
        print(f"{folder_path}/ does not exist")

print("\nDone! All scans, history, and uploaded images have been cleared.")
