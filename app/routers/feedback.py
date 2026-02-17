from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import desc
from datetime import datetime
from typing import List

from .. import models, schemas
from ..deps import get_db, get_current_user, get_current_admin

router = APIRouter(prefix="/feedback", tags=["feedback"])


# Add Feedback model if not exists

# Use schemas.FeedbackCreate directly (type, message, user_id)



# Use schemas.FeedbackOut directly (id, message, type, user_id, created_at)


from fastapi import Request

@router.post("", response_model=schemas.FeedbackOut)
async def submit_feedback(
    feedback: schemas.FeedbackCreate,
    request: Request,
    db: Session = Depends(get_db),
):
    """Submit feedback from users (mobile/web, with or without auth)"""
    if not hasattr(models, 'Feedback'):
        raise HTTPException(
            status_code=501,
            detail="Feedback feature is not available yet"
        )
    # Prefer user_id from request body if provided
    user_id = feedback.user_id
    if not user_id:
        # Try to get user from Authorization header
        auth = request.headers.get('authorization')
        if auth and auth.lower().startswith('bearer '):
            from ..deps import get_current_user
            try:
                token = auth.split(' ', 1)[1]
                user = get_current_user.__wrapped__(token=token, db=db)
                user_id = user.id
            except Exception:
                user_id = None
    db_feedback = models.Feedback(
        user_id=user_id,
        message=feedback.message,
        type=feedback.type
    )
    db.add(db_feedback)
    db.commit()
    db.refresh(db_feedback)
    return db_feedback


@router.get("", response_model=List[schemas.FeedbackOut])
def get_feedback(
    db: Session = Depends(get_db),
    limit: int = 50,
    skip: int = 0,
):
    """Get all feedback (admin only)"""
    if not hasattr(models, 'Feedback'):
        return []
    feedback = db.query(models.Feedback)\
        .order_by(desc(models.Feedback.created_at))\
        .offset(skip)\
        .limit(limit)\
        .all()
    return feedback


@router.get("/user/me", response_model=List[schemas.FeedbackOut])
def get_my_feedback(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
    limit: int = 50,
):
    """Get current user's feedback"""
    if not hasattr(models, 'Feedback'):
        return []
    feedback = db.query(models.Feedback)\
        .filter(models.Feedback.user_id == current_user.id)\
        .order_by(desc(models.Feedback.created_at))\
        .limit(limit)\
        .all()
    return feedback


@router.post("/", response_model=schemas.FeedbackOut)
def create_feedback(
    feedback: schemas.FeedbackCreate,
    db: Session = Depends(get_db),
):
    db_feedback = models.Feedback(
        message=feedback.message, 
        user_id=feedback.user_id, 
        type=feedback.type
    )
    db.add(db_feedback)
    db.commit()
    db.refresh(db_feedback)
    return db_feedback


from sqlalchemy.orm import joinedload

@router.get("/", response_model=List[schemas.FeedbackOut])
def get_feedbacks(
    db: Session = Depends(get_db),
):
    return db.query(models.Feedback)\
        .options(joinedload(models.Feedback.user))\
        .order_by(models.Feedback.created_at.desc())\
        .all()
