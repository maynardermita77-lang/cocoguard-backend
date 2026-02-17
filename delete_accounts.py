from app.database import SessionLocal
from app.models import User

# List of emails/usernames to delete
TO_DELETE = [
    'farmer@cocoguard.com',
    'maynard@cocoguard.com',
    'maynardermita@gmail.com',
    'marimar@gmail.com',
    'menong@gmail.com',
    'maynard.ermita13@gmail.com',
    'admin@cocoguard.com',
    'test@test.com',
    'farmer',
    'maynard',
    'farmermaynard',
    'juskomarimar',
    'menong',
    'menard',
    'admin',
    'testuser',
]

def delete_accounts():
    db = SessionLocal()
    try:
        deleted = 0
        for identifier in TO_DELETE:
            user = db.query(User).filter((User.email == identifier) | (User.username == identifier)).first()
            if user:
                db.delete(user)
                deleted += 1
        db.commit()
        print(f"Deleted {deleted} user(s) from the database.")
    except Exception as e:
        print(f"Error: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    delete_accounts()
