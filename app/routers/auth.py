from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.orm import Session
from datetime import datetime, timedelta, timezone
import random
import string
import logging

from .. import models, schemas
from ..auth_utils import get_password_hash, verify_password, create_access_token
from ..deps import get_db, get_current_user
from ..services.email_service import send_password_reset_email

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["auth"])


def generate_verification_code() -> str:
    """Generate a 6-digit verification code"""
    return ''.join(random.choices(string.digits, k=6))


@router.post("/register", response_model=schemas.TokenWithUser)
def register(data: schemas.UserCreate, db: Session = Depends(get_db)):
    # Check email uniqueness
    if db.query(models.User).filter(models.User.email == data.email).first():
        raise HTTPException(status_code=400, detail="Email already registered")
    
    # Check username uniqueness
    if db.query(models.User).filter(models.User.username == data.username).first():
        raise HTTPException(status_code=400, detail="Username already taken")

    # Hash password
    hashed_password = get_password_hash(data.password)

    # Create user object mapping EXACT SQL COLUMN NAMES
    new_user = models.User(
        username=data.username,
        email=data.email,
        password_hash=hashed_password,  # VERY IMPORTANT
        full_name=data.full_name,
        phone=data.phone,
        gender=data.gender,
        date_of_birth=data.date_of_birth,
        address_line=data.address_line,
        region=data.region,
        province=data.province,
        city=data.city,
        barangay=data.barangay,
        role=models.UserRole.user
    )

    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    # Create JWT token (use user ID as subject for consistency with login)
    token = create_access_token({"sub": str(new_user.id)})

    return schemas.TokenWithUser(
        access_token=token,
        token_type="bearer",
        user=new_user
    )


@router.post("/login", response_model=schemas.TokenWithUser)
def login(login_in: schemas.LoginRequest, db: Session = Depends(get_db)):
    q = db.query(models.User).filter(
        (models.User.email == login_in.email_or_username)
        | (models.User.username == login_in.email_or_username)
    )
    user = q.first()
    if not user or not verify_password(login_in.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    if user.status == models.UserStatus.inactive:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is deactivated. Please contact admin.")

    token = create_access_token({"sub": str(user.id)})
    return schemas.TokenWithUser(access_token=token, user=user)


@router.get("/me")
def get_current_user_info(
    current_user: models.User = Depends(get_current_user),
):
    """Get current authenticated user information"""
    return {
        "id": current_user.id,
        "username": current_user.username,
        "email": current_user.email,
        "full_name": current_user.full_name,
        "phone": current_user.phone,
        "gender": current_user.gender,
        "date_of_birth": current_user.date_of_birth,
        "address_line": current_user.address_line,
        "region": current_user.region,
        "province": current_user.province,
        "city": current_user.city,
        "barangay": current_user.barangay,
        "role": current_user.role,
        "status": current_user.status,
        "created_at": current_user.created_at,
        "updated_at": current_user.updated_at,
    }


@router.put("/me")
def update_current_user(
    data: schemas.UserUpdate,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update current authenticated user information"""
    # Update only provided fields
    if data.full_name is not None:
        current_user.full_name = data.full_name
    if data.phone is not None:
        current_user.phone = data.phone
    if data.gender is not None:
        current_user.gender = data.gender
    if data.date_of_birth is not None:
        current_user.date_of_birth = data.date_of_birth
    if data.address_line is not None:
        current_user.address_line = data.address_line
    if data.region is not None:
        current_user.region = data.region
    if data.province is not None:
        current_user.province = data.province
    if data.city is not None:
        current_user.city = data.city
    if data.barangay is not None:
        current_user.barangay = data.barangay
    
    db.commit()
    db.refresh(current_user)
    
    return {
        "success": True,
        "message": "Profile updated successfully",
        "user": {
            "id": current_user.id,
            "username": current_user.username,
            "email": current_user.email,
            "full_name": current_user.full_name,
            "phone": current_user.phone,
            "gender": current_user.gender,
            "date_of_birth": current_user.date_of_birth,
            "address_line": current_user.address_line,
            "region": current_user.region,
            "province": current_user.province,
            "city": current_user.city,
            "barangay": current_user.barangay,
            "role": current_user.role,
            "status": current_user.status,
        }
    }


@router.post("/change-password")
def change_password(
    data: schemas.ChangePasswordRequest,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # Verify current password
    if not verify_password(data.current_password, current_user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect"
        )
    
    # Validate new password length
    if len(data.new_password) < 6:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New password must be at least 6 characters"
        )
    
    # Hash and update new password
    current_user.password_hash = get_password_hash(data.new_password)
    db.commit()
    
    return {"message": "Password changed successfully"}


@router.post("/change-password/request-code")
async def request_change_password_code(
    data: schemas.ChangePasswordRequest,
    background_tasks: BackgroundTasks,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Request verification code for changing password.
    Verifies current password first, then sends code to user's email.
    """
    # Verify current password
    if not verify_password(data.current_password, current_user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect"
        )
    
    # Validate new password length
    if len(data.new_password) < 6:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New password must be at least 6 characters"
        )
    
    # Invalidate any existing unused tokens for this user
    db.query(models.PasswordResetToken).filter(
        models.PasswordResetToken.user_id == current_user.id,
        models.PasswordResetToken.is_used == False
    ).update({"is_used": True})
    db.commit()
    
    # Generate new verification code
    code = generate_verification_code()
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=15)
    
    # Create verification token
    reset_token = models.PasswordResetToken(
        user_id=current_user.id,
        token=code,
        email=current_user.email,
        expires_at=expires_at
    )
    db.add(reset_token)
    db.commit()
    
    # Send email in background
    background_tasks.add_task(
        send_password_reset_email,
        to_email=current_user.email,
        code=code,
        username=current_user.username or current_user.full_name or ""
    )
    
    logger.info(f"Change password verification code sent to {current_user.email}")
    
    return {
        "success": True,
        "message": "A 6-digit verification code has been sent to your email.",
        "email": current_user.email
    }


@router.post("/change-password/verify")
async def verify_and_change_password(
    data: schemas.ChangePasswordWithCode,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Verify code and change password.
    """
    # Verify current password again for security
    if not verify_password(data.current_password, current_user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect"
        )
    
    # Validate new password length
    if len(data.new_password) < 6:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New password must be at least 6 characters"
        )
    
    # Find the verification token
    token = db.query(models.PasswordResetToken).filter(
        models.PasswordResetToken.user_id == current_user.id,
        models.PasswordResetToken.token == data.code,
        models.PasswordResetToken.is_used == False
    ).first()
    
    if not token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired verification code"
        )
    
    # Check if token is expired
    now = datetime.now(timezone.utc)
    token_expires = token.expires_at
    if token_expires.tzinfo is None:
        token_expires = token_expires.replace(tzinfo=timezone.utc)
    
    if now > token_expires:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Verification code has expired. Please request a new one."
        )
    
    # Update password
    current_user.password_hash = get_password_hash(data.new_password)
    
    # Mark token as used
    token.is_used = True
    
    db.commit()
    
    logger.info(f"Password changed successfully for user: {current_user.email}")
    
    return {
        "success": True,
        "message": "Password changed successfully"
    }


@router.post("/logout")
def logout(current_user: models.User = Depends(get_current_user)):
    """
    Logout current user.
    Since we use stateless JWTs, this is mainly a signal endpoint.
    The client is expected to clear its stored token.
    """
    logger.info(f"User logged out: {current_user.email}")
    return {"success": True, "message": "Logged out successfully"}


@router.post("/logout-all")
def logout_all_devices(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Sign out from all devices.
    Invalidates all password reset tokens and returns confirmation.
    Since we use stateless JWTs, full token revocation is not supported,
    but this clears any active verification tokens.
    """
    # Invalidate all password reset tokens for this user
    db.query(models.PasswordResetToken).filter(
        models.PasswordResetToken.user_id == current_user.id,
        models.PasswordResetToken.is_used == False
    ).update({"is_used": True})
    db.commit()

    logger.info(f"User signed out from all devices: {current_user.email}")
    return {"success": True, "message": "Signed out from all devices. All active sessions will expire shortly."}


@router.delete("/delete-account")
def delete_account(
    data: schemas.DeleteAccountRequest,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Permanently delete the current user's account and all associated data.
    Requires password verification.
    """
    # Verify password
    if not verify_password(data.current_password, current_user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password is incorrect"
        )

    user_email = current_user.email
    user_id = current_user.id

    try:
        # Delete user settings
        db.query(models.UserSettings).filter(
            models.UserSettings.user_id == user_id
        ).delete()

        # Delete password reset tokens
        db.query(models.PasswordResetToken).filter(
            models.PasswordResetToken.user_id == user_id
        ).delete()

        # Delete feedbacks
        db.query(models.Feedback).filter(
            models.Feedback.user_id == user_id
        ).delete()

        # Delete scans
        from .scans import _delete_scan_image
        user_scans = db.query(models.Scan).filter(
            models.Scan.user_id == user_id
        ).all()
        for scan in user_scans:
            _delete_scan_image(scan.image_url)
            db.delete(scan)

        # Delete farms
        db.query(models.Farm).filter(
            models.Farm.user_id == user_id
        ).delete()

        # Delete the user
        db.delete(current_user)
        db.commit()

        logger.info(f"Account deleted successfully for user: {user_email} (ID: {user_id})")

        return {
            "success": True,
            "message": "Account and all associated data have been permanently deleted."
        }
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to delete account for user {user_email}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete account. Please try again."
        )



