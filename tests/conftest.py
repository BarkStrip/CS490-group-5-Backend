"""
Pytest configuration and shared fixtures for the salon app tests.
"""

import pytest
import os
import bcrypt
from main import create_app
from app.extensions import db as database
from flask import Flask

# UPDATED: Absolute imports matching your actual models.py classes
from app.models import AuthUser, Customers, SalonOwners, Salon, Service, SalonVerify


@pytest.fixture(scope="session")
def app():
    """Create and configure a test app instance."""
    os.environ["FLASK_ENV"] = "testing"
    os.environ["TESTING"] = "True"

    app = create_app()

    # Use your local MySQL with the specific test database
    app.config.update(
        {
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": os.environ.get(
                "MYSQL_PUBLIC_URL",
                "mysql+pymysql://root:test_password@127.0.0.1:3306/salon_app_test",
            ),
            "SECRET_KEY": "test-secret-key-for-testing-only",
            "WTF_CSRF_ENABLED": False,
        }
    )

    yield app


@pytest.fixture(scope="session")
def db(app: Flask):
    """Create test database using Base metadata."""
    from app.models import Base

    with app.app_context():
        # Drop existing tables
        Base.metadata.drop_all(bind=database.engine)

        # Create tables from models.py
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
            except:
                pass

        # Replace remove temporarily
        database.session.remove = safe_remove

        yield database.session

        # Restore original remove
        database.session.remove = original_remove

        # Cleanup
        try:
            database.session.rollback()
        except:
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
        email="customer@example.com",  # Note: Added based on common patterns, remove if not in DB schema
        phone_number="123-456-7890",
        gender="Non-binary",
    )
    db_session.add(customer)
    db_session.commit()

    return customer


@pytest.fixture
def sample_owner(db_session):
    """Create a sample salon owner (AuthUser + SalonOwners profile)."""
    # 1. Create AuthUser
    hashed_pw = bcrypt.hashpw(b"ownerpass123", bcrypt.gensalt())
    auth_user = AuthUser(
        email="owner@example.com",
        password_hash=hashed_pw,
        role="OWNER",  # Enum value from models.py
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
