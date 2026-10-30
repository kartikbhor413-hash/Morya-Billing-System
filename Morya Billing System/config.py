import os
from datetime import timedelta
from dotenv import load_dotenv

# Load .env file
load_dotenv()

class Config:
    SECRET_KEY = os.getenv("FLASK_SECRET_KEY", "moraya_electric_ultra_secure_billing_key_9988771122")
    
    # Supabase Configuration
    SUPABASE_URL = os.getenv("SUPABASE_URL", "https://cehyxvndblmzdttsfkca.supabase.co").rstrip("/")
    SUPABASE_KEY = os.getenv("SUPABASE_KEY", "").strip()
    SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip()
    
    # Session Settings
    PERMANENT_SESSION_LIFETIME = timedelta(days=7)
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = False  # Set to True in HTTPS production
    
    # Business Details
    BUSINESS_NAME = os.getenv("BUSINESS_NAME", "MORAYA ELECTRIC")
    BUSINESS_TAGLINE = os.getenv("BUSINESS_TAGLINE", "Electrical & Electronics Solutions")
    BUSINESS_PHONE = os.getenv("BUSINESS_PHONE", "7083155192, 8625914505")
    BUSINESS_ADDRESS = os.getenv("BUSINESS_ADDRESS", "Main Road, Maharashtra")
    
    # Admin Credentials
    ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "admin@moraya.com").lower()
    ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "Admin@Moraya2026")
    ADMIN_NAME = os.getenv("ADMIN_NAME", "Admin")

    # The 8 Mandatory Default Services
    DEFAULT_SERVICES = [
        "House Wiring",
        "House and Building Maintenance",
        "AC Point",
        "Geyser Point",
        "Geyser Repairing",
        "Fan Repairing",
        "Fan Installation",
        "Geyser Installation"
    ]
