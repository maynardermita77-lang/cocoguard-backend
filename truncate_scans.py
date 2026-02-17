from app.database import SessionLocal
from app.models import Scan

def truncate_scans():
    db = SessionLocal()
    try:
        deleted = db.query(Scan).delete()
        db.commit()
        print(f"Deleted {deleted} scan(s) from the scans table.")
    except Exception as e:
        print(f"Error: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    truncate_scans()
