from app.database import SessionLocal
from app.models import Feedback

def truncate_feedback():
    db = SessionLocal()
    try:
        deleted = db.query(Feedback).delete()
        db.commit()
        print(f"Deleted {deleted} feedback(s) from the feedback table.")
    except Exception as e:
        print(f"Error: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    truncate_feedback()
