import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

# Application
APP_NAME = "GmailToSkillSheetMatcherForSES"
VERSION = "0.1.0"
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")
DEBUG = ENVIRONMENT == "development"
SECRET_KEY = os.getenv("APP_SECRET_KEY", "dev-secret-key")

# Gmail API Configuration
GMAIL = {
    "client_id": os.getenv("GOOGLE_CLIENT_ID"),
    "client_secret": os.getenv("GOOGLE_CLIENT_SECRET"),
    "redirect_uri": os.getenv("GOOGLE_REDIRECT_URI"),
    "scopes": [
        "https://www.googleapis.com/auth/gmail.readonly",
        "https://www.googleapis.com/auth/gmail.modify"
    ]
}

# File Storage
UPLOAD_FOLDER = BASE_DIR / "uploads"
PROCESSED_FOLDER = BASE_DIR / "processed"

# Create necessary directories
for directory in [UPLOAD_FOLDER, PROCESSED_FOLDER]:
    directory.mkdir(exist_ok=True)

# Logging Configuration
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_CONFIG = {
    "handlers": [
        {"sink": "logs/app.log", "rotation": "10 MB", "level": LOG_LEVEL},
        {"sink": "logs/error.log", "rotation": "10 MB", "level": "ERROR"},
    ],
    "extra": {"app_name": APP_NAME, "environment": ENVIRONMENT}
}
