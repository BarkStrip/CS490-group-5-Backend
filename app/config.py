import os

# MySQL connection
url = os.environ.get("MYSQL_PUBLIC_URL")
if not url:
    raise ValueError("MYSQL_PUBLIC_URL environment variable is required")

if url and not url.startswith("mysql+pymysql://"):
    url = url.replace("mysql://", "mysql+pymysql://", 1)

# S3 config
S3_BUCKET_NAME = os.environ.get("S3_BUCKET_NAME")
S3_REGION = os.environ.get("AWS_REGION")  # Corrected to match .env
S3_BASE_URL = os.environ.get("S3_BASE_URL")

# --- ADDED PRINT STATEMENTS ---
print("--- Loading Flask Config ---")
print(f"S3_BUCKET_NAME: {S3_BUCKET_NAME}")
print(f"S3_REGION (from AWS_REGION): {S3_REGION}")
print(f"S3_BASE_URL: {S3_BASE_URL}")
print(f"DATABASE_URL_LOADED: {'Yes' if url else 'No'}")
print("----------------------------")
# --- END ---

class Config:
    SQLALCHEMY_DATABASE_URI = url
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SECRET_KEY = os.environ.get("SECRET_KEY", "supersecretdevkey123")

    S3_BUCKET_NAME = S3_BUCKET_NAME
    S3_REGION = S3_REGION
    S3_BASE_URL = S3_BASE_URL