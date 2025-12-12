import pytest
import json
import uuid
from datetime import date, datetime
from app.models import (
    Customers, 
    AuthUser, 
    PayMethod, 
    Salon, 
    LoyaltyProgram, 
    LoyaltyAccount, 
    LoyaltyTransaction,
    Order
)

# -------------------------------------------------------------------
# Fixtures
# -------------------------------------------------------------------

@pytest.fixture
def payment_data(db_session, sample_owner):
    """
    Creates:
    1. A Customer
    2. A default Payment Method
    3. A Salon with Loyalty Program
    """
    unique_id = str(uuid.uuid4())[:8]

    # 1. Customer
    u = AuthUser(email=f"pay_{unique_id}@t.com", password_hash=b"x", role="CUSTOMER", firebase_uid=f"u_{unique_id}")
    db_session.add(u)
    db_session.flush()
    
    c = Customers(user_id=u.id, first_name="Pay", last_name="Test")
    db_session.add(c)
    db_session.flush()

    # 2. Existing Payment Method (Default)
    pm = PayMethod(
        user_id=c.id,
        card_name="Test Visa",
        brand="Visa",
        last4="4242",
        Expiration=date(2025, 12, 1),
        is_default=True
    )
    db_session.add(pm)

    # 3. Salon & Loyalty
    salon = Salon(salon_owner_id=sample_owner.id, name="Loyalty Salon", city="Cash City", latitude=0, longitude=0)
    db_session.add(salon)
    db_session.flush()

    prog = LoyaltyProgram(
        salon_id=salon.id, 
        active=True, 
        points_per_dollar=1.0, 
        points_for_reward=100, 
        reward_value=10.0
    )
    db_session.add(prog)
    
    # Loyalty Account with some points
    acct = LoyaltyAccount(user_id=c.id, salon_id=salon.id, points=200)
    db_session.add(acct)
    
    db_session.commit()

    return {
        "customer_id": c.id,
        "method_id": pm.id,
        "salon_id": salon.id,
        "account_id": acct.id
    }

# -------------------------------------------------------------------
# Test Class
# -------------------------------------------------------------------

@pytest.mark.payments
class TestPaymentMethods:

    # --- GET METHODS ---
    def test_get_methods_success(self, client, payment_data):
        """Test retrieving payment methods for a customer."""
        cid = payment_data["customer_id"]
        response = client.get(f"/api/payments/{cid}/methods")
        
        assert response.status_code == 200
        data = response.json
        assert len(data) >= 1
        assert data[0]["last4"] == "4242"
        assert data[0]["is_default"] is True

    def test_get_methods_customer_not_found(self, client):
        """Test 404 if customer doesn't exist."""
        response = client.get("/api/payments/999999/methods")
        assert response.status_code == 404

    # --- CREATE METHODS ---
    def test_create_method_success(self, client, payment_data):
        """Test adding a new payment method."""
        cid = payment_data["customer_id"]
        payload = {
            "card_name": "New Mastercard",
            "brand": "Mastercard",
            "last4": "5555",
            "expiration": "10/26",
            "is_default": 0
        }
        response = client.post(f"/api/payments/{cid}/methods", json=payload)
        
        assert response.status_code == 201
        data = response.json
        assert data["last4"] == "5555"
        assert data["brand"] == "Mastercard"

    def test_create_method_validation_error(self, client, payment_data):

        cid = payment_data["customer_id"]
        
        payload = {
            "card_name": "Bad Date",
            "brand": "Visa",
            "last4": "1111",
            "expiration": "13/99"  # Invalid month
        }
        resp = client.post(f"/api/payments/{cid}/methods", json=payload)
        assert resp.status_code == 400
        assert "MM/YY" in resp.json["error"]

        # Case 2: Bad last4
        payload["expiration"] = "12/25"
        payload["last4"] = "123"
        resp = client.post(f"/api/payments/{cid}/methods", json=payload)
        assert resp.status_code == 400
        assert "exactly 4 digits" in resp.json["error"]


    def test_set_default_method(self, client, payment_data, db_session):
        """Test switching default card."""
        cid = payment_data["customer_id"]
        
        second_card = PayMethod(
            user_id=cid,
            card_name="Second",
            brand="Visa",
            last4="2222",
            Expiration=date(2026, 1, 1),
            is_default=False
        )
        db_session.add(second_card)
        db_session.commit()
        
        response = client.put(f"/api/payments/{cid}/methods/{second_card.id}/set-default")
        
        assert response.status_code == 200
        assert response.json["is_default"] is True
        
        db_session.expire_all()
        
        old_default = db_session.get(PayMethod, payment_data["method_id"])
        assert not old_default.is_default

    def test_set_default_wrong_customer(self, client, payment_data, db_session):
        unique_id = str(uuid.uuid4())[:8]
        other_auth = AuthUser(
            email=f"other_{unique_id}@t.com", 
            password_hash=b"x", 
            role="CUSTOMER", 
            firebase_uid=f"ou_{unique_id}"
        )
        db_session.add(other_auth)
        db_session.flush()

        other_user = Customers(user_id=other_auth.id, first_name="Stranger") 
        db_session.add(other_user)
        db_session.flush()
        
        other_card = PayMethod(user_id=other_user.id, last4="0000", is_default=False)
        db_session.add(other_card)
        db_session.commit()
        
        cid = payment_data["customer_id"] 
        
        resp = client.put(f"/api/payments/{cid}/methods/{other_card.id}/set-default")
        assert resp.status_code == 403

    def test_delete_method(self, client, payment_data, db_session):
        """Test deleting a payment method."""
        cid = payment_data["customer_id"]
        mid = payment_data["method_id"]
        
        response = client.delete(f"/api/payments/{cid}/methods/{mid}")
        assert response.status_code == 200
        
        db_session.expire_all()

        found = db_session.get(PayMethod, mid)
        assert found is None

    def test_create_order_with_loyalty(self, client, payment_data, db_session):
        """
        Test create_order endpoint.
        """
        cid = payment_data["customer_id"]
        sid = payment_data["salon_id"]
        
        payload = {
            "customer_id": cid,
            "salon_id": sid,
            "cart_items": [
                {
                    "salon_id": sid,
                    "kind": "service",
                    "unit_price": 50.0,
                    "qty": 1
                }
            ],
            "subtotal": 50.0,
            "total_amnt": 50.0,
            "applied_rewards": [],
            "promo_id": None 
        }
        
        response = client.post("/api/payments/create_order", json=payload)
        
        assert response.status_code == 201
        order_id = response.json["order_id"]
        assert order_id is not None
        
        db_session.expire_all()

        acct = db_session.get(LoyaltyAccount, payment_data["account_id"])
        assert acct.points == 250

    def test_create_order_loyalty_redemption(self, client, payment_data, db_session):
        cid = payment_data["customer_id"]
        sid = payment_data["salon_id"]
        
        payload = {
            "customer_id": cid,
            "salon_id": sid,
            "cart_items": [
                {"salon_id": sid, "unit_price": 20.0, "qty": 1}
            ],
            "total_amnt": 10.0, 
            "applied_rewards": [
                {"salon_id": sid, "discount_amount": 10.0}
            ],
            "promo_id": None
        }
        
        response = client.post("/api/payments/create_order", json=payload)
        assert response.status_code == 201
        
        db_session.expire_all()

        acct = db_session.get(LoyaltyAccount, payment_data["account_id"])
        assert acct.points == 120