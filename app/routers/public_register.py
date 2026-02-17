from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr
from datetime import datetime, timedelta, timezone, date
from typing import Optional
import secrets
import logging
from .. import models
from ..deps import get_db
from ..auth_utils import get_password_hash, create_access_token
from ..services.email_service import send_verification_email

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/public-register", tags=["public-register"])


# ---------- Request Schemas ----------

class SendRegisterCodeRequest(BaseModel):
    recipient: EmailStr


class RegisterAdminVerifiedRequest(BaseModel):
    email: EmailStr
    password: str
    code: str


class RegisterWithVerifiedEmailRequest(BaseModel):
    """Full registration after email has been verified with a code."""
    email: EmailStr
    password: str
    code: str
    full_name: str
    username: str
    phone: Optional[str] = None
    gender: Optional[str] = None
    date_of_birth: Optional[date] = None
    address_line: Optional[str] = None
    region: Optional[str] = None
    province: Optional[str] = None
    city: Optional[str] = None
    barangay: Optional[str] = None


class GoogleSignInRequest(BaseModel):
    """Google Sign-In: send id_token from Google."""
    id_token: str
    # Optional profile fields for first-time sign-up
    full_name: Optional[str] = None
    phone: Optional[str] = None
    gender: Optional[str] = None
    date_of_birth: Optional[date] = None
    address_line: Optional[str] = None
    region: Optional[str] = None
    province: Optional[str] = None
    city: Optional[str] = None
    barangay: Optional[str] = None


class GoogleSignInV2Request(BaseModel):
    """Google Sign-In v2: send access_token + user-chosen password."""
    access_token: str
    password: str


class VerifyEmailCodeRequest(BaseModel):
    """Verify an email code without registering (just validation)."""
    email: EmailStr
    code: str


# ---------- Endpoints ----------

@router.post("/send-verification-code")
async def send_register_verification_code(data: SendRegisterCodeRequest, db: Session = Depends(get_db)):
    """Send a 6-digit verification code to an email for registration."""
    # Check if email already exists
    if db.query(models.User).filter(models.User.email == data.recipient).first():
        raise HTTPException(status_code=400, detail="Email already registered")
    # Invalidate any previous unused codes for this email
    db.query(models.VerificationCode).filter(
        models.VerificationCode.recipient == data.recipient,
        models.VerificationCode.type == "email",
        models.VerificationCode.is_used == False
    ).update({"is_used": True})
    db.commit()

    code = ''.join(secrets.choice('0123456789') for _ in range(6))
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=10)
    verification = models.VerificationCode(
        user_id=None,
        code=code,
        type="email",
        recipient=data.recipient,
        expires_at=expires_at
    )
    db.add(verification)
    db.commit()
    await send_verification_email(data.recipient, code)
    logger.info(f"Registration verification code sent to {data.recipient}")
    return {"success": True, "message": "Verification code sent to email."}


@router.post("/verify-code")
def verify_email_code(data: VerifyEmailCodeRequest, db: Session = Depends(get_db)):
    """Verify a code sent to an email (does not consume it - registration will consume it)."""
    code_obj = db.query(models.VerificationCode).filter(
        models.VerificationCode.recipient == data.email,
        models.VerificationCode.code == data.code,
        models.VerificationCode.type == "email",
        models.VerificationCode.is_used == False
    ).order_by(models.VerificationCode.created_at.desc()).first()
    if not code_obj:
        raise HTTPException(status_code=400, detail="Invalid verification code.")
    now = datetime.now(timezone.utc)
    exp = code_obj.expires_at
    if exp.tzinfo is None:
        exp = exp.replace(tzinfo=timezone.utc)
    if now > exp:
        raise HTTPException(status_code=400, detail="Verification code has expired. Please request a new one.")
    return {"success": True, "message": "Code is valid.", "verified": True}


@router.post("/register-verified")
def register_with_verified_email(data: RegisterWithVerifiedEmailRequest, db: Session = Depends(get_db)):
    """Complete user registration after email verification."""
    # Check email uniqueness
    if db.query(models.User).filter(models.User.email == data.email).first():
        raise HTTPException(status_code=400, detail="Email already registered")
    # Check username uniqueness
    if db.query(models.User).filter(models.User.username == data.username).first():
        raise HTTPException(status_code=400, detail="Username already taken")
    # Find and consume the verification code
    code_obj = db.query(models.VerificationCode).filter(
        models.VerificationCode.recipient == data.email,
        models.VerificationCode.code == data.code,
        models.VerificationCode.type == "email",
        models.VerificationCode.is_used == False
    ).order_by(models.VerificationCode.created_at.desc()).first()
    if not code_obj:
        raise HTTPException(status_code=400, detail="Invalid or expired verification code.")
    now = datetime.now(timezone.utc)
    exp = code_obj.expires_at
    if exp.tzinfo is None:
        exp = exp.replace(tzinfo=timezone.utc)
    if now > exp:
        raise HTTPException(status_code=400, detail="Verification code has expired. Please request a new one.")
    code_obj.is_used = True
    db.commit()

    # Create user
    hashed_password = get_password_hash(data.password)
    new_user = models.User(
        username=data.username,
        email=data.email,
        password_hash=hashed_password,
        full_name=data.full_name,
        phone=data.phone,
        gender=data.gender,
        date_of_birth=data.date_of_birth,
        address_line=data.address_line,
        region=data.region,
        province=data.province,
        city=data.city,
        barangay=data.barangay,
        role=models.UserRole.user,
        status=models.UserStatus.active,
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    token = create_access_token({"sub": str(new_user.id)})
    logger.info(f"New user registered with verified email: {data.email}")
    return {
        "success": True,
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "id": new_user.id,
            "username": new_user.username,
            "email": new_user.email,
            "full_name": new_user.full_name,
            "phone": new_user.phone,
            "gender": new_user.gender,
            "date_of_birth": str(new_user.date_of_birth) if new_user.date_of_birth else None,
            "address_line": new_user.address_line,
            "region": new_user.region,
            "province": new_user.province,
            "city": new_user.city,
            "barangay": new_user.barangay,
            "role": new_user.role,
            "status": new_user.status,
        },
    }


@router.post("/google-signin")
async def google_sign_in(data: GoogleSignInRequest, db: Session = Depends(get_db)):
    """
    Sign in or register with Google.
    Verifies the Google ID token, then:
      - If user exists: log them in and return a JWT.
      - If user is new: create an account and return a JWT.
    """
    from google.oauth2 import id_token as google_id_token
    from google.auth.transport import requests as google_requests

    try:
        idinfo = google_id_token.verify_oauth2_token(
            data.id_token,
            google_requests.Request(),
        )
        google_email = idinfo.get("email")
        google_name = idinfo.get("name", "")
        if not google_email:
            raise HTTPException(status_code=400, detail="Google token missing email.")
        if not idinfo.get("email_verified", False):
            raise HTTPException(status_code=400, detail="Google email not verified.")
    except ValueError as e:
        logger.error(f"Google token verification failed: {e}")
        raise HTTPException(status_code=401, detail="Invalid Google ID token.")

    # Check if user already exists
    existing_user = db.query(models.User).filter(models.User.email == google_email).first()
    if existing_user:
        if existing_user.status == models.UserStatus.inactive:
            raise HTTPException(status_code=403, detail="Account is deactivated. Please contact admin.")
        token = create_access_token({"sub": str(existing_user.id)})
        return {
            "success": True,
            "is_new_user": False,
            "access_token": token,
            "token_type": "bearer",
            "user": {
                "id": existing_user.id,
                "username": existing_user.username,
                "email": existing_user.email,
                "full_name": existing_user.full_name,
                "phone": existing_user.phone,
                "gender": existing_user.gender,
                "date_of_birth": str(existing_user.date_of_birth) if existing_user.date_of_birth else None,
                "address_line": existing_user.address_line,
                "region": existing_user.region,
                "province": existing_user.province,
                "city": existing_user.city,
                "barangay": existing_user.barangay,
                "role": existing_user.role,
                "status": existing_user.status,
            },
        }

    # New user: create account
    # Generate a unique username from email
    base_username = google_email.split("@")[0]
    username = base_username
    counter = 1
    while db.query(models.User).filter(models.User.username == username).first():
        username = f"{base_username}{counter}"
        counter += 1

    # Google users get a random password hash (they log in via Google)
    random_pw = secrets.token_urlsafe(32)
    hashed_password = get_password_hash(random_pw)

    new_user = models.User(
        username=username,
        email=google_email,
        password_hash=hashed_password,
        full_name=data.full_name or google_name or base_username,
        phone=data.phone,
        gender=data.gender,
        date_of_birth=data.date_of_birth,
        address_line=data.address_line,
        region=data.region,
        province=data.province,
        city=data.city,
        barangay=data.barangay,
        role=models.UserRole.user,
        status=models.UserStatus.active,
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    token = create_access_token({"sub": str(new_user.id)})
    logger.info(f"New user registered via Google: {google_email}")
    return {
        "success": True,
        "is_new_user": True,
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "id": new_user.id,
            "username": new_user.username,
            "email": new_user.email,
            "full_name": new_user.full_name,
            "phone": new_user.phone,
            "gender": new_user.gender,
            "date_of_birth": str(new_user.date_of_birth) if new_user.date_of_birth else None,
            "address_line": new_user.address_line,
            "region": new_user.region,
            "province": new_user.province,
            "city": new_user.city,
            "barangay": new_user.barangay,
            "role": new_user.role,
            "status": new_user.status,
        },
    }


@router.post("/google-signin-v2")
async def google_sign_in_v2(data: GoogleSignInV2Request, db: Session = Depends(get_db)):
    """
    Sign in or register with Google using an OAuth2 access_token + a user-chosen password.
    Verifies the access_token via Google's userinfo endpoint, then:
      - If user exists: update password, log them in, return JWT.
      - If user is new: create account with the given password, return JWT.
    This avoids the People API dependency and ensures every Google user has a usable password.
    """
    import requests as http_req

    # Verify access token by calling Google's userinfo endpoint
    try:
        resp = http_req.get(
            'https://www.googleapis.com/oauth2/v3/userinfo',
            headers={'Authorization': f'Bearer {data.access_token}'},
            timeout=10,
        )
        if resp.status_code != 200:
            logger.error(f"Google userinfo returned {resp.status_code}: {resp.text}")
            raise HTTPException(status_code=401, detail="Invalid Google access token.")
        user_info = resp.json()
    except http_req.RequestException as e:
        logger.error(f"Google userinfo request failed: {e}")
        raise HTTPException(status_code=401, detail="Could not verify Google token.")

    google_email = user_info.get('email')
    google_name = user_info.get('name', '')
    if not google_email:
        raise HTTPException(status_code=400, detail="Google token missing email.")
    if not user_info.get('email_verified', False):
        raise HTTPException(status_code=400, detail="Google email is not verified.")

    # Validate password
    if not data.password or len(data.password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters.")

    hashed_password = get_password_hash(data.password)

    # Check if user already exists
    existing_user = db.query(models.User).filter(models.User.email == google_email).first()
    if existing_user:
        if existing_user.status == models.UserStatus.inactive:
            raise HTTPException(status_code=403, detail="Account is deactivated. Please contact admin.")
        # Update password so user can login with email + password
        existing_user.password_hash = hashed_password
        db.commit()
        token = create_access_token({"sub": str(existing_user.id)})
        logger.info(f"Existing user signed in via Google (password updated): {google_email}")
        return {
            "success": True,
            "is_new_user": False,
            "access_token": token,
            "token_type": "bearer",
            "user": {
                "id": existing_user.id,
                "username": existing_user.username,
                "email": existing_user.email,
                "full_name": existing_user.full_name,
                "phone": existing_user.phone,
                "gender": existing_user.gender,
                "date_of_birth": str(existing_user.date_of_birth) if existing_user.date_of_birth else None,
                "address_line": existing_user.address_line,
                "region": existing_user.region,
                "province": existing_user.province,
                "city": existing_user.city,
                "barangay": existing_user.barangay,
                "role": existing_user.role,
                "status": existing_user.status,
            },
        }

    # New user: create account with user-chosen password
    base_username = google_email.split("@")[0]
    username = base_username
    counter = 1
    while db.query(models.User).filter(models.User.username == username).first():
        username = f"{base_username}{counter}"
        counter += 1

    new_user = models.User(
        username=username,
        email=google_email,
        password_hash=hashed_password,
        full_name=google_name or base_username,
        role=models.UserRole.user,
        status=models.UserStatus.active,
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    token = create_access_token({"sub": str(new_user.id)})
    logger.info(f"New user registered via Google v2 (with password): {google_email}")
    return {
        "success": True,
        "is_new_user": True,
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "id": new_user.id,
            "username": new_user.username,
            "email": new_user.email,
            "full_name": new_user.full_name,
            "phone": new_user.phone,
            "gender": new_user.gender,
            "date_of_birth": str(new_user.date_of_birth) if new_user.date_of_birth else None,
            "address_line": new_user.address_line,
            "region": new_user.region,
            "province": new_user.province,
            "city": new_user.city,
            "barangay": new_user.barangay,
            "role": new_user.role,
            "status": new_user.status,
        },
    }


@router.post("/register-admin-verified")
def register_admin_verified(data: RegisterAdminVerifiedRequest, db: Session = Depends(get_db)):
    """Register an admin account after email verification."""
    if db.query(models.User).filter(models.User.email == data.email).first():
        raise HTTPException(status_code=400, detail="Email already registered")
    code_obj = db.query(models.VerificationCode).filter(
        models.VerificationCode.recipient == data.email,
        models.VerificationCode.code == data.code,
        models.VerificationCode.type == "email",
        models.VerificationCode.expires_at > datetime.now(timezone.utc),
        models.VerificationCode.is_used == False
    ).first()
    if not code_obj:
        raise HTTPException(status_code=400, detail="Invalid or expired verification code.")
    code_obj.is_used = True
    db.commit()
    hashed_password = get_password_hash(data.password)
    new_user = models.User(
        username=data.email.split('@')[0],
        email=data.email,
        password_hash=hashed_password,
        role=models.UserRole.admin,
        status=models.UserStatus.active
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return {"success": True, "message": "Admin account created successfully."}
