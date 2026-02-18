from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
import os
import traceback


from .database import engine, Base
from .config import settings
from .routers import auth, users, pest_types, scans, farms, uploads, feedback, knowledge, analytics, verification, settings as settings_router, prediction, password_reset, notifications, two_factor, management_strategies, survey, public_register

# Create tables on startup
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: create tables
    Base.metadata.create_all(bind=engine)
    # Create uploads directory
    os.makedirs(settings.upload_dir, exist_ok=True)
    
    # Seed database with default admin account if empty
    try:
        from .database import SessionLocal
        from .models import User, UserRole, UserStatus, PestType, PestRiskLevel
        from .auth_utils import get_password_hash
        db = SessionLocal()
        
        # Seed admin accounts
        user_count = db.query(User).count()
        if user_count == 0:
            print("[INFO] Empty database detected — seeding default admin accounts...")
            admins = [
                {
                    "username": "Admin",
                    "email": "admin@cocoguard.com",
                    "password": "cocoguard",
                    "full_name": "Administrator",
                    "role": UserRole.admin,
                },
                {
                    "username": "maynardermita",
                    "email": "maynardermita@gmail.com",
                    "password": "cocoguard",
                    "full_name": "Maynard Ermita",
                    "role": UserRole.admin,
                },
                {
                    "username": "erwincmartinez",
                    "email": "erwincmartinez.cgc@gmail.com",
                    "password": "cocoguard",
                    "full_name": "Erwin Martinez",
                    "role": UserRole.admin,
                },
                {
                    "username": "maynardermita77",
                    "email": "maynardermita77@gmail.com",
                    "password": "cocoguard",
                    "full_name": "Maynard Ermita",
                    "role": UserRole.user,
                },
            ]
            for acct in admins:
                new_user = User(
                    username=acct["username"],
                    email=acct["email"],
                    password_hash=get_password_hash(acct["password"]),
                    role=acct["role"],
                    status=UserStatus.active,
                    full_name=acct["full_name"],
                )
                db.add(new_user)
            db.commit()
            print(f"[INFO] Seeded {len(admins)} default admin accounts")
        else:
            print(f"[INFO] Database has {user_count} users, skipping user seed")
        
        # Seed pest types
        pest_count = db.query(PestType).count()
        if pest_count == 0:
            print("[INFO] No pest types found — seeding default pest types...")
            default_pests = [
                {"name": "APW Adult", "scientific_name": "Rhynchophorus ferrugineus", "risk_level": PestRiskLevel.critical},
                {"name": "APW Larvae", "scientific_name": "Rhynchophorus ferrugineus", "risk_level": PestRiskLevel.critical},
                {"name": "Brontispa", "scientific_name": "Brontispa longissima", "risk_level": PestRiskLevel.high},
                {"name": "Brontispa Pupa", "scientific_name": "Brontispa longissima", "risk_level": PestRiskLevel.medium},
                {"name": "Rhinoceros Beetle", "scientific_name": "Oryctes rhinoceros", "risk_level": PestRiskLevel.critical},
                {"name": "Slug Caterpillar", "scientific_name": "Parasa lepida", "risk_level": PestRiskLevel.medium},
                {"name": "White Grub", "scientific_name": "Leucopholis irrorata", "risk_level": PestRiskLevel.high},
            ]
            for pest in default_pests:
                db.add(PestType(**pest, is_active=True))
            db.commit()
            print(f"[INFO] Seeded {len(default_pests)} pest types")
        else:
            print(f"[INFO] Database has {pest_count} pest types, skipping pest seed")
        
        db.close()
    except Exception as e:
        print(f"[WARNING] Database seeding error: {e}")
    
    # Pre-load prediction model
    try:
        from .services.prediction_service import get_prediction_service
        service = get_prediction_service()
        print(f"[INFO] Prediction model loaded: {service.model_loaded}")
        print(f"[INFO] Available pest classes: {service.labels}")
    except Exception as e:
        print(f"[WARNING] Failed to pre-load prediction model: {e}")
    
    yield
    # Shutdown: cleanup if needed

app = FastAPI(
    title=settings.api_title,
    version=settings.api_version,
    description=settings.api_description,
    lifespan=lifespan
)

# Define allowed origins explicitly
allowed_origins = [
    "http://localhost",
    "http://localhost:80",
    "http://localhost:3000",
    "http://127.0.0.1",
    "http://127.0.0.1:80",
    "http://10.0.0.17",
    "http://10.0.0.17:80",
    "http://10.0.0.17:8000",
    "https://cocoguard-web.pages.dev",
    "https://cocoguard-backend.onrender.com",
    "*",  # Fallback for development
]

# Allow frontends to call this API - with explicit CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)


# Global exception handler to ensure CORS headers are always sent
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Catch all exceptions and return proper JSON with CORS headers"""
    print(f"[ERROR] Unhandled exception: {exc}")
    print(f"[ERROR] Traceback: {traceback.format_exc()}")
    
    # Get origin from request
    origin = request.headers.get("origin", "*")
    
    return JSONResponse(
        status_code=500,
        content={
            "detail": str(exc),
            "error": "Internal Server Error"
        },
        headers={
            "Access-Control-Allow-Origin": origin,
            "Access-Control-Allow-Credentials": "true",
            "Access-Control-Allow-Methods": "*",
            "Access-Control-Allow-Headers": "*",
        }
    )

# Routers
app.include_router(auth.router)
app.include_router(users.router)
app.include_router(farms.router)
app.include_router(pest_types.router)
app.include_router(scans.router)
app.include_router(uploads.router)
app.include_router(feedback.router)
app.include_router(knowledge.router)
app.include_router(analytics.router)
app.include_router(verification.router)
app.include_router(settings_router.router)
app.include_router(prediction.router)
app.include_router(password_reset.router)
app.include_router(notifications.router)
app.include_router(two_factor.router)
app.include_router(management_strategies.router)
app.include_router(survey.router)
app.include_router(public_register.router)


# Mount /test_static after imports so os is defined
test_static_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '../test_static'))
if os.path.isdir(test_static_dir):
    print(f"[DEBUG] Mounting /test_static from: {test_static_dir}")
    print(f"[DEBUG] Files in {test_static_dir}: {os.listdir(test_static_dir)}")
    app.mount(
        "/test_static",
        StaticFiles(directory=test_static_dir),
        name="test_static"
    )



# Always use the correct absolute path for static serving

# Serve static files from the backend's own uploads directory
uploads_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '../uploads/files'))
print(f"[DEBUG] Absolute uploads_dir path: {uploads_dir}")
os.makedirs(uploads_dir, exist_ok=True)  # Create if not exists
if os.path.isdir(uploads_dir):
    print(f"[DEBUG] Serving /uploads/files from: {uploads_dir}")
    try:
        print(f"[DEBUG] Files in {uploads_dir}: {os.listdir(uploads_dir)}")
    except Exception as e:
        print(f"[DEBUG] Could not list files in {uploads_dir}: {e}")
    from starlette.requests import Request
    from starlette.responses import Response
    from fastapi.staticfiles import StaticFiles as _StaticFiles
    import os
    
    class CORSStaticFiles(_StaticFiles):
        """Static files handler with CORS headers for cross-origin image loading"""
        async def get_response(self, path: str, scope):
            resolved_path = os.path.abspath(os.path.join(self.directory, path))
            print(f"[DEBUG] Static file requested: {path}")
            print(f"[DEBUG] Resolved file path: {resolved_path}")
            response = await super().get_response(path, scope)
            # Add CORS headers to all static file responses
            response.headers["Access-Control-Allow-Origin"] = "*"
            response.headers["Access-Control-Allow-Methods"] = "GET, OPTIONS"
            response.headers["Access-Control-Allow-Headers"] = "*"
            response.headers["Cache-Control"] = "public, max-age=3600"
            return response
    
    app.mount(
        "/uploads/files",
        CORSStaticFiles(directory=uploads_dir),
        name="uploads"
    )
else:
    print(f"WARNING: uploads/files directory not found at {uploads_dir}")

# Serve scan images from uploads/scans directory
scans_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '../uploads/scans'))
print(f"[DEBUG] Absolute scans_dir path: {scans_dir}")
os.makedirs(scans_dir, exist_ok=True)  # Create if not exists
if os.path.isdir(scans_dir):
    print(f"[DEBUG] Serving /uploads/scans from: {scans_dir}")
    try:
        scan_files = os.listdir(scans_dir)
        print(f"[DEBUG] Found {len(scan_files)} files in scans directory")
    except Exception as e:
        print(f"[DEBUG] Could not list files in {scans_dir}: {e}")
    app.mount(
        "/uploads/scans",
        CORSStaticFiles(directory=scans_dir),
        name="scans"
    )
else:
    print(f"WARNING: uploads/scans directory not found at {scans_dir}")


@app.get("/")
def read_root():
    return {"message": "CocoGuard API is running"}


@app.get("/health")
def health_check():
    """Health check endpoint for connectivity testing"""
    return {"status": "healthy", "service": "CocoGuard API"}
