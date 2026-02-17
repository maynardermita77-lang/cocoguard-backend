"""
Fix verification_codes table: make user_id nullable.
SQLite doesn't support ALTER COLUMN, so we recreate the table.
"""
import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "cocoguard.db")

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

print("Fixing verification_codes table: making user_id nullable...")

# 1. Rename old table
cursor.execute("ALTER TABLE verification_codes RENAME TO verification_codes_old;")

# 2. Create new table with user_id nullable
cursor.execute("""
CREATE TABLE verification_codes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    code VARCHAR(6) NOT NULL,
    type VARCHAR(20) NOT NULL,
    recipient VARCHAR(255) NOT NULL,
    is_used BOOLEAN DEFAULT 0,
    created_at DATETIME,
    expires_at DATETIME NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id)
);
""")

# 3. Copy existing data
cursor.execute("""
INSERT INTO verification_codes (id, user_id, code, type, recipient, is_used, created_at, expires_at)
SELECT id, user_id, code, type, recipient, is_used, created_at, expires_at
FROM verification_codes_old;
""")

# 4. Drop old table
cursor.execute("DROP TABLE verification_codes_old;")

conn.commit()
conn.close()

print("Done! verification_codes.user_id is now nullable.")
