from app.models import AuthUser, Customers, SalonOwners, Salon, Service, SalonVerify

"""
Pytest configuration and shared fixtures for the salon app tests.
"""

import pytest
import os
import bcrypt
from main import create_app
from app.extensions import db as database
from flask import Flask
import sys
from pathlib import Path
from dotenv import load_dotenv

test_env_path = Path(__file__).parent / ".env.test"
if test_env_path.exists():
    load_dotenv(test_env_path, override=True)
    print(f" Loaded test environment from: {test_env_path}")
else:
    print(f" WARNING: .env.test not found at {test_env_path}")
    print(" Create a .env.test file with MYSQL_TEST_URL pointing to a test database!")
    # sys.exit(1)


def is_safe_test_database(db_uri: str) -> bool:
    """
    Check if the database URI is safe for testing.
    Returns False if it appears to be a production database.
    """
    if not db_uri:
        return False

    # Check for production indicators - INCLUDING YOUR PRODUCTION HOST
    dangerous_patterns = [
        "nozomi.proxy.rlwy.net",
        "railway.internal",
        "amazonaws.com",
        "azure.com",
        "googlecloud",
        "prod",
        "production",
        "live",
        "main",
        "t_salon_app",
    ]

    # Check for test indicators
    safe_patterns = [
        "salon_app_test",
        "test",
        "testing",
        "localhost",
        "127.0.0.1",
        "dev",
        "development",
    ]

    db_uri_lower = db_uri.lower()

    # If it contains dangerous patterns, it's not safe
    for pattern in dangerous_patterns:
        if pattern in db_uri_lower:
            print(f" DANGER: Found production pattern '{pattern}' in database URL!")
            return False

    # Must contain at least one safe pattern
    for pattern in safe_patterns:
        if pattern in db_uri_lower:
            return True

    return False


@pytest.fixture(scope="session")
def app():
    """Create and configure a test app instance."""
    os.environ["FLASK_ENV"] = "testing"
    os.environ["TESTING"] = "True"

    # CRITICAL: Use a separate test database URL
    # Never use MYSQL_PUBLIC_URL directly as it might be production!
    test_db_url = os.environ.get("MYSQL_TEST_URL")

    if not test_db_url:
        print(" MYSQL_TEST_URL not found in environment!")
        print(" Make sure .env.test is loaded and contains MYSQL_TEST_URL")
        sys.exit(1)

    # Safety check
    if not is_safe_test_database(test_db_url):
        print(f" DANGER: Database URL appears to be production: {test_db_url}")
        print(" Tests aborted to prevent data loss!")
        print(" Please set MYSQL_TEST_URL to a test database")
        sys.exit(1)

    app = create_app()

    # Override ANY database configuration from the main app
    app.config.update(
        {
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": test_db_url,
            "SECRET_KEY": "test-secret-key-for-testing-only",
            "WTF_CSRF_ENABLED": False,
        }
    )

    # Double-check we're not using production
    actual_db_uri = app.config.get("SQLALCHEMY_DATABASE_URI", "")
    if "nozomi.proxy.rlwy.net" in actual_db_uri or "t_salon_app" in actual_db_uri:
        print(" CRITICAL: App is still configured with production database!")
        print(" Database URI: {actual_db_uri}")
        sys.exit(1)

    print(f"✅ Running tests against: {test_db_url}")

    yield app


@pytest.fixture(scope="session")
def db(app: Flask):
    """Create test database using Base metadata."""
    from app.models import Base

    with app.app_context():
        # Double-check we're in test mode
        if not app.config.get("TESTING"):
            print(" DANGER: Not in testing mode!")
            sys.exit(1)

        db_uri = app.config.get("SQLALCHEMY_DATABASE_URI", "")

        # Final safety check before dropping tables
        if not is_safe_test_database(db_uri):
            print(
                f" DANGER: About to drop tables in what appears to be production: {db_uri}"
            )
            print(" Tests aborted to prevent data loss!")
            sys.exit(1)

        # Additional explicit check for your production database
        if "nozomi.proxy.rlwy.net" in db_uri or "t_salon_app" in db_uri:
            print(" CRITICAL ERROR: ATTEMPTING TO DROP PRODUCTION TABLES!")
            print(" Database: {db_uri}")
            print(" STOPPING IMMEDIATELY!")
            sys.exit(1)

        # Only drop tables if we're absolutely sure it's a test database
        print("🧹 Dropping tables in test database...")
        Base.metadata.drop_all(bind=database.engine)

        print("📦 Creating tables in test database...")
        Base.metadata.create_all(bind=database.engine)

        yield database

        database.session.remove()
        Base.metadata.drop_all(bind=database.engine)


@pytest.fixture
def db_session(app, db):
    """Create a database session that properly rollbacks after each test."""

    with app.app_context():
        # Begin a transaction
        connection = database.engine.connect()
        transaction = connection.begin()

        # Configure the session
        database.session.configure(bind=connection)

        # Save original remove method
        original_remove = database.session.remove

        # Create a custom remove that doesn't fail
        def safe_remove():
            try:
                database.session.rollback()
                database.session.expunge_all()
            except Exception:
                pass

        # Replace remove temporarily
        database.session.remove = safe_remove

        yield database.session

        # Restore original remove
        database.session.remove = original_remove

        # Cleanup
        try:
            database.session.rollback()
        except Exception:
            pass

        transaction.rollback()
        connection.close()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def runner(app):
    return app.test_cli_runner()


@pytest.fixture
def sample_customer(db_session):
    """Create a sample customer (AuthUser + Customers profile)."""
    # 1. Create the AuthUser first
    hashed_pw = bcrypt.hashpw(b"password123", bcrypt.gensalt())
    auth_user = AuthUser(
        email="customer@example.com",
        password_hash=hashed_pw,
        role="CUSTOMER",
        firebase_uid="test_uid_123",
    )
    db_session.add(auth_user)
    db_session.flush()  # Flush to generate auth_user.id

    # 2. Create the Customer profile linked to AuthUser
    customer = Customers(
        user_id=auth_user.id,
        first_name="Test",
        last_name="Customer",
        email="customer@example.com",
        phone_number="123-456-7890",
        gender="Non-binary",
    )
    db_session.add(customer)
    db_session.commit()

    return customer


@pytest.fixture
def sample_owner(db_session):
    """Create a sample salon owner (AuthUser + SalonOwners profile)."""
    # 1. Create AuthUser Test1
    hashed_pw = bcrypt.hashpw(b"ownerpass123", bcrypt.gensalt())
    auth_user = AuthUser(
        email="owner@example.com",
        password_hash=hashed_pw,
        role="OWNER",
        firebase_uid="owner_uid_456",
    )
    db_session.add(auth_user)
    db_session.flush()

    # 2. Create Owner Profile
    owner = SalonOwners(
        user_id=auth_user.id,
        first_name="Salon",
        last_name="Owner",
        phone_number="987-654-3210",
        address="Owner Address",
    )
    db_session.add(owner)
    db_session.commit()

    return owner


@pytest.fixture
def sample_salon(db_session, sample_owner):
    """Create a sample salon linked to the sample_owner."""
    # 1. Create Salon
    # Note: owner_id in your old code is likely salon_owner_id in new models
    salon = Salon(
        salon_owner_id=sample_owner.id,
        name="Test Salon",
        address="123 Test St",
        city="Newark",
        latitude=40.735660,
        longitude=-74.172370,
        phone="123-456-7890",
        about="Best salon in Newark",
    )
    db_session.add(salon)
    db_session.flush()

    # 2. Add verification
    verify = SalonVerify(
        salon_id=salon.id, status="APPROVED"  # Enum: PENDING, APPROVED, REJECTED
    )
    db_session.add(verify)
    db_session.flush()

    # 3. Add a service
    service = Service(
        salon_id=salon.id, name="Haircut", price=50.00, duration=60, is_active=1
    )
    db_session.add(service)
    db_session.commit()

    return salon


@pytest.fixture
def test_user_data():
    """Provide a dictionary of user data for signup/login tests."""
    return {
        "email": "newuser122@example.com",
        "password": "password123",
        "first_name": "New",
        "last_name": "User",
        "phone_number": "555-0199",
        "role": "CUSTOMER",
        "gender": "Prefer not to say",
    }


@pytest.fixture
def test_gettype():
    """Provide a dictionary of user data for signup/login tests."""
    return {
        "email": "newuser23@example.com",
        "password": "password1234",
        "first_name": "New",
        "last_name": "User",
        "phone_number": "555-0199",
        "role": "CUSTOMER",
        "gender": "Prefer not to say",
    }


@pytest.fixture
def auth_headers(client, db_session):
    """
    Get authorization headers.
    Note: We create a fresh user here to ensure no ID conflicts.
    """
    # Create a user specifically for login testing
    hashed_pw = bcrypt.hashpw(b"password123", bcrypt.gensalt())
    user = AuthUser(
        email="login_test@example.com",
        password_hash=hashed_pw,
        role="CUSTOMER",
        firebase_uid="login_uid_789",
    )
    db_session.add(user)
    db_session.commit()

    # Perform login request
    response = client.post(
        "/api/auth/login",
        json={"email": "login_test@example.com", "password": "password123"},
    )

    if response.status_code == 200:
        token = response.json.get("token")
        return {"Authorization": f"Bearer {token}"}

    return {}
