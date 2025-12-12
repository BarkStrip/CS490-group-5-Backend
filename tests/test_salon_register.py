import pytest

import uuid
from datetime import time
from app.models import (
    AuthUser,
    SalonOwners,
    Salon,
    SalonHours,
    Service,
    Product,
    SalonVerify,
    Types,
)


@pytest.fixture
def salon_types(db_session):
    t1 = Types(name="Hair")
    t2 = Types(name="Nails")
    db_session.add(t1)
    db_session.add(t2)
    db_session.commit()
    return [t1, t2]


@pytest.fixture
def unique_email():
    """Generate a unique email for each test run."""
    return f"reg_{uuid.uuid4().hex[:8]}@example.com"


@pytest.mark.salon_register
class TestSalonRegisterEndpoint:
    """Tests for POST /api/salon_register/register"""

    def test_register_success(self, client, db_session, salon_types, unique_email):
        payload = {
            "owner": {
                "name": "Jane Doe",
                "email": unique_email,
                "password": "securePass123",
                "phone": "555-0000",
            },
            "salon": {
                "name": "Luxe Salon",
                "address": "123 Main St",
                "city": "Newark",
                "state": "NJ",
                "zip": "07102",
                "phone": "555-SALON",
                "tags": ["Hair", "Nails"],
                "latitude": 40.7357,
                "longitude": -74.1724,
            },
            "hours": {
                "monday": {"open": "09:00", "close": "17:00"},
                "tuesday": {"closed": True},
            },
            "services": [{"name": "Basic Cut", "price": 50.0, "duration": 45}],
            "terms_agreed": True,
            "business_confirmed": True,
        }

        response = client.post("/api/salon_register/register", json=payload)

        # 1. Check Response
        assert response.status_code == 201
        data = response.json
        assert data["status"] == "success"
        assert "salon_id" in data

        salon_id = data["salon_id"]

        # Owner & User
        owner_user = db_session.query(AuthUser).filter_by(email=unique_email).first()
        assert owner_user is not None
        assert owner_user.role == "OWNER"

        owner_profile = (
            db_session.query(SalonOwners).filter_by(user_id=owner_user.id).first()
        )
        assert owner_profile.first_name == "Jane"
        assert owner_profile.last_name == "Doe"

        # Salon
        salon = db_session.get(Salon, salon_id)
        assert salon.name == "Luxe Salon"
        assert len(salon.type) == 2
        # Hours (Monday Open, Tuesday Closed)
        # Sunday = 0, Monday = 1, ...
        mon_hours = (
            db_session.query(SalonHours).filter_by(salon_id=salon_id, weekday=1).first()
        )
        assert mon_hours is not None
        assert mon_hours.is_open == 1
        assert mon_hours.open_time == time(9, 0)

        tue_hours = (
            db_session.query(SalonHours).filter_by(salon_id=salon_id, weekday=2).first()
        )
        assert tue_hours is not None
        assert tue_hours.is_open == 0
        # Service
        svc = (
            db_session.query(Service)
            .filter_by(salon_id=salon_id, name="Basic Cut")
            .first()
        )
        assert svc is not None
        assert svc.price == 50.0

        # Verification
        verify = db_session.query(SalonVerify).filter_by(salon_id=salon_id).first()
        assert verify.status == "PENDING"

    def test_register_duplicate_email(self, client, unique_email):
        """Test that registering with an existing email fails."""
        # 1. Register once
        payload = {
            "owner": {"name": "A", "email": unique_email, "password": "p"},
            "salon": {"name": "S", "tags": ["Hair"]},  # Min required
            "terms_agreed": True,
            "business_confirmed": True,
        }
        client.post("/api/salon_register/register", json=payload)

        # 2. Register again
        response = client.post("/api/salon_register/register", json=payload)

        assert response.status_code == 409
        assert "Email already registered" in response.json["message"]

    def test_register_missing_fields(self, client):
        """Test validation logic."""
        # Missing owner email
        payload = {
            "owner": {"name": "No Email"},
            "salon": {"name": "S"},
            "terms_agreed": True,
            "business_confirmed": True,
        }
        response = client.post("/api/salon_register/register", json=payload)
        assert response.status_code == 400
        assert "Owner information incomplete" in response.json["message"]

    def test_register_missing_tags(self, client):
        """Test validation for missing tags."""
        payload = {
            "owner": {"name": "N", "email": "e@e.com", "password": "p"},
            "salon": {"name": "S", "tags": []},  # Empty tags
            "terms_agreed": True,
            "business_confirmed": True,
        }
        response = client.post("/api/salon_register/register", json=payload)
        assert response.status_code == 400
        assert "select at least one salon category" in response.json["message"]


@pytest.mark.salon_register
class TestServiceManagement:
    """Tests for /add_service and /delete_service"""

    @pytest.fixture
    def setup_salon(self, db_session):
        # Create a basic salon to add services to
        owner_user = AuthUser(
            email=f"svc_{uuid.uuid4().hex[:6]}@e.com", password_hash=b"p", role="OWNER"
        )
        db_session.add(owner_user)
        db_session.flush()
        owner = SalonOwners(user_id=owner_user.id)
        db_session.add(owner)
        db_session.flush()
        salon = Salon(
            salon_owner_id=owner.id, name="Svc Salon", latitude=0, longitude=0
        )
        db_session.add(salon)
        db_session.commit()
        return salon

    def test_add_service_success(self, client, setup_salon):
        """Test adding a service via form data."""
        data = {
            "name": "New Service",
            "salon_id": setup_salon.id,
            "price": "25.00",
            "duration": "30",
        }
        # Note: Using data=data sends multipart/form-data
        response = client.post("/api/salon_register/add_service", data=data)

        assert response.status_code == 201
        resp_data = response.json
        assert resp_data["service"]["name"] == "New Service"
        assert resp_data["service"]["price"] == 25.0

    def test_add_service_duplicate(self, client, setup_salon, db_session):
        """Test adding a duplicate service name."""
        # Pre-create service
        svc = Service(salon_id=setup_salon.id, name="Dup Service", price=10)
        db_session.add(svc)
        db_session.commit()

        data = {"name": "Dup Service", "salon_id": setup_salon.id, "price": "20"}
        response = client.post("/api/salon_register/add_service", data=data)

        assert response.status_code == 409
        assert "already exists" in response.json["error"]

    def test_delete_service(self, client, setup_salon, db_session):
        """Test deleting a service."""
        svc = Service(salon_id=setup_salon.id, name="To Delete", price=10)
        db_session.add(svc)
        db_session.commit()

        response = client.delete(f"/api/salon_register/delete_service/{svc.id}")
        assert response.status_code == 200

        # Verify deletion
        assert db_session.get(Service, svc.id) is None


@pytest.mark.salon_register
class TestProductManagement:
    """Tests for /add_product and /delete_product"""

    @pytest.fixture
    def setup_salon(self, db_session):
        owner_user = AuthUser(
            email=f"prod_{uuid.uuid4().hex[:6]}@e.com", password_hash=b"p", role="OWNER"
        )
        db_session.add(owner_user)
        db_session.flush()
        owner = SalonOwners(user_id=owner_user.id)
        db_session.add(owner)
        db_session.flush()
        salon = Salon(
            salon_owner_id=owner.id, name="Prod Salon", latitude=0, longitude=0
        )
        db_session.add(salon)
        db_session.commit()
        return salon

    def test_add_product_success(self, client, setup_salon):
        data = {
            "name": "Gel Polish",
            "salon_id": setup_salon.id,
            "price": "15.00",
            "stock_qty": "100",
            "sku": "GP-001",
        }
        response = client.post("/api/salon_register/add_product", data=data)

        assert response.status_code == 201
        assert response.json["product"]["name"] == "Gel Polish"
        assert response.json["product"]["sku"] == "GP-001"

    def test_delete_product(self, client, setup_salon, db_session):
        prod = Product(salon_id=setup_salon.id, name="Old Prod", price=5)
        db_session.add(prod)
        db_session.commit()

        response = client.delete(f"/api/salon_register/delete_product/{prod.id}")
        assert response.status_code == 200
        assert db_session.get(Product, prod.id) is None


@pytest.mark.salon_register
class TestVerificationStatus:
    """Tests for GET /<id>/verification_status"""

    def test_get_status_success(self, client, db_session):
        # Setup
        user = AuthUser(
            email=f"ver_{uuid.uuid4().hex}@e.com", password_hash=b"p", role="OWNER"
        )
        db_session.add(user)
        db_session.flush()
        owner = SalonOwners(user_id=user.id)
        db_session.add(owner)
        db_session.flush()
        salon = Salon(salon_owner_id=owner.id, name="V Salon", latitude=0, longitude=0)
        db_session.add(salon)
        db_session.flush()

        # Add Verification
        verify = SalonVerify(salon_id=salon.id, status="APPROVED")
        db_session.add(verify)
        db_session.commit()

        response = client.get(f"/api/salon_register/{salon.id}/verification_status")

        assert response.status_code == 200
        assert response.json["status"] == "APPROVED"

    def test_get_status_salon_not_found(self, client):
        response = client.get("/api/salon_register/999999/verification_status")
        assert response.status_code == 404
