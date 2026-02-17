from pydantic_settings import BaseSettings
from pydantic import ConfigDict, field_validator
import os

class Settings(BaseSettings):
    # API Info
    api_title: str = "CocoGuard API"
    api_version: str = "1.0.0"
    api_description: str = "Coconut Pest Detection and Management System"
    
    # Database
    database_url: str = "sqlite:///./cocoguard.db"
    
    # Security
    secret_key: str = "change-this-secret-key-to-a-long-random-string"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 1440  # 24 hours
    
    # File Upload
    max_upload_size: int = 5242880  # 5MB
    upload_dir: str = "./uploads"
    
    # Email Configuration
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_from_email: str = ""
    smtp_from_name: str = "CocoGuard"
    
    # SMS Configuration (Twilio)
    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_phone_number: str = ""

    # CORS (stored as raw string to avoid JSON parsing errors from env)
    allowed_origins_raw: str = "*"
    
    model_config = ConfigDict(env_file=".env", case_sensitive=False)

    @field_validator('allowed_origins_raw', mode='before')
    @classmethod
    def validate_origins(cls, v):
        return v or "*"

    @property
    def allowed_origins(self):
        # Split comma-separated values; default to ["*"]
        raw = (self.allowed_origins_raw or "*").strip()
        return [item.strip() for item in raw.split(",") if item.strip()] or ["*"]

settings = Settings()
