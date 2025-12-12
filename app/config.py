import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# In case pytest tests/ -v -s is run, it will only read .env.test
if "pytest" in sys.modules or os.environ.get("TESTING") == "True":
    test_env_path = Path(__file__).parent.parent / "tests" / ".env.test"
    if test_env_path.exists():
        load_dotenv(test_env_path, override=True)
        print(f" Loaded test environment from: {test_env_path}")

# Determine if we're in testing mode
TESTING = os.environ.get("TESTING") == "True"
FLASK_ENV = os.environ.get("FLASK_ENV")


def is_production_database(db_url: str) -> bool:
    """Check if a database URL appears to be production."""
    if not db_url:
        return False

    dangerous_patterns = [
        "nozomi.proxy.rlwy.net",
        "railway.app",
        "railway.internal",
        "rlwy.net",
        "t_salon_app",
        "production",
        "live",
        "amazonaws.com",
        "azure.com",
    ]

    for pattern in dangerous_patterns:
        if pattern in db_url.lower():
            return True
    return False


def is_test_database(db_url: str) -> bool:
    """Check if a database URL appears to be for testing."""
    if not db_url:
        return False

    safe_patterns = ["salon_app_test", "localhost", "127.0.0.1", "test"]

    for pattern in safe_patterns:
        if pattern in db_url.lower():
            return True
    return False


if TESTING or FLASK_ENV == "testing":

    # First try to get test URL from environment
    url = os.environ.get("MYSQL_TEST_URL")

    if not url:
        # Default to a local test database
        url = "mysql+pymysql://root:mysql2025@localhost:3306/salon_app_test"
        print("⚠️  MYSQL_TEST_URL not set, using default local test database")

    # CRITICAL SAFETY CHECK: Make sure we're not using production
    if is_production_database(url):
        print(" CRITICAL ERROR: Test is trying to use production database!")
        print(f" Database URL contains production patterns: {url}")
        print(" Aborting to prevent data loss!")
        sys.exit(1)

    # Verify it looks like a test database
    if not is_test_database(url):
        print("  WARNING: Database URL doesn't look like a test database")
        print(f"  URL: {url}")
        print("  Consider adding 'test' to the database name")

    prod_url = os.environ.get("MYSQL_PUBLIC_URL")
    if prod_url and is_production_database(prod_url):
        # Clear it to prevent any accidental usage
        os.environ.pop("MYSQL_PUBLIC_URL", None)
        print("  Blocked access to production database during testing")

    print(" TESTING MODE: Using test database")

else:
    # FOR PRODUCTION/DEVELOPMENT: Use the normal database
    url = os.environ.get("MYSQL_PUBLIC_URL")

    if not url:
        # In development, fall back to local database
        if FLASK_ENV == "development":
            url = "mysql+pymysql://root:password@127.0.0.1:3306/salon_app_dev"
            print("  MYSQL_PUBLIC_URL not set, using local development database")
        else:
            raise ValueError(
                "MYSQL_PUBLIC_URL environment variable is required for production"
            )

    # Warning if using production database
    if is_production_database(url):
        print("  WARNING: Using production database - be careful!")

    print(f" {FLASK_ENV or 'PRODUCTION'} MODE: Using main database")

# Fix MySQL URL format if needed
if url and not url.startswith("mysql+pymysql://"):
    url = url.replace("mysql://", "mysql+pymysql://", 1)

# Final safety check
if TESTING and is_production_database(url):
    print(" FINAL SAFETY CHECK FAILED: Cannot use production database in tests!")
    sys.exit(1)

# S3 config
S3_BUCKET_NAME = os.environ.get("S3_BUCKET_NAME")
S3_REGION = os.environ.get("AWS_REGION")
S3_BASE_URL = os.environ.get("S3_BASE_URL")

print("\n" + "=" * 70)
print("CONFIGURATION SUMMARY")
print("=" * 70)
print(f"Environment: {FLASK_ENV or 'production'}")
print(f"Testing Mode: {TESTING}")
if url and "@" in url:
    parts = url.split("@")
    protocol_user = parts[0].split("://")[0] + "://****:****"
    host_db = parts[1]
    print(f"Database: {protocol_user}@{host_db}")
else:
    print("Database: configured")
print(f"S3 Bucket: {S3_BUCKET_NAME}")
print(f"S3 Region: {S3_REGION}")
print("=" * 70 + "\n")


class Config:
    SQLALCHEMY_DATABASE_URI = url
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SECRET_KEY = os.environ.get("SECRET_KEY", "supersecretdevkey123")

    # Add testing flag to config
    TESTING = TESTING

    # S3 Configuration
    S3_BUCKET_NAME = S3_BUCKET_NAME
    S3_REGION = S3_REGION
    S3_BASE_URL = S3_BASE_URL

    # Additional safety property
    @property
    def is_safe_for_testing(self):
        """Double-check that we're not using production database in tests."""
        if self.TESTING:
            return not is_production_database(self.SQLALCHEMY_DATABASE_URI)
        return True
