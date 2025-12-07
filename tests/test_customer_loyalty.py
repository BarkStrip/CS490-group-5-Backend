import pytest
import uuid
from datetime import datetime
from sqlalchemy import select
from app.models import (
    AuthUser,
    Customers,
    Salon,
    SalonOwners,
    LoyaltyProgram,
    LoyaltyAccount,
    Appointment,
    LoyaltyTransaction,
)

# ---------------------------------------------------------------------------- #
#                                Local Fixtures                                #
# ---------------------------------------------------------------------------- #


@pytest.fixture
def loyalty_fixtures(db_session):
    """
    Sets up a complete loyalty ecosystem:
    1. Salon Owner & Salon
    2. Customer
    3. Loyalty Program (Points Based)
    4. Loyalty Account (Customer linked to Salon)
    5. Appointments (Past visits)
    """
    # 1. Salon Setup
    uid = str(uuid.uuid4())[:8]
    owner_user = AuthUser(
        email=f"loyalty_owner_{uid}@example.com",
        password_hash=b"pass",
        role="OWNER",
        firebase_uid=f"uid_owner_{uid}",
    )
    db_session.add(owner_user)
    db_session.flush()

    owner = SalonOwners(user_id=owner_user.id, first_name="Points", last_name="Owner")
    db_session.add(owner)
    db_session.flush()

    salon = Salon(
        salon_owner_id=owner.id,
        name="Loyalty Salon",
        city="Rewards City",
        latitude=40.0,
        longitude=-74.0,
        phone="555-9999",
    )
    db_session.add(salon)
    db_session.flush()

    # 2. Loyalty Program Setup
    program = LoyaltyProgram(
        salon_id=salon.id,
        active=True,
        program_type="POINTS",
        points_per_dollar=2.0,  # Earn 2 points per $1
        points_for_reward=100,  # 100 points needed for reward
        reward_type="FIXED_AMOUNT",
        reward_value=10.00,  # $10 off
        reward_description="$10 Off Reward",
    )
    db_session.add(program)

    # 3. Customer Setup
    cust_uid = str(uuid.uuid4())[:8]
    cust_user = AuthUser(
        email=f"loyalty_cust_{cust_uid}@example.com",
        password_hash=b"pass",
        role="CUSTOMER",
        firebase_uid=f"uid_cust_{cust_uid}",
    )
    db_session.add(cust_user)
    db_session.flush()

    customer = Customers(user_id=cust_user.id, first_name="Loyal", last_name="Shopper")
    db_session.add(customer)
    db_session.flush()

    # 4. Loyalty Account Setup (User starts with 150 points)
    account = LoyaltyAccount(user_id=customer.id, salon_id=salon.id, points=150)
    db_session.add(account)
    db_session.flush()

    # 5. Add a past transaction
    txn = LoyaltyTransaction(
        loyalty_account_id=account.id, points_change=150, reason="INITIAL_BONUS"
    )
    db_session.add(txn)

    # 6. Add a completed appointment (to test visit counts)
    appt = Appointment(
        customer_id=customer.id,
        salon_id=salon.id,
        start_at=datetime.now(),
        end_at=datetime.now(),
        status="COMPLETED",
    )
    db_session.add(appt)

    db_session.commit()

    return {
        "customer": customer,
        "salon": salon,
        "program": program,
        "account": account,
        "appointment": appt,
    }


# ---------------------------------------------------------------------------- #
#                                 Test Classes                                 #
# ---------------------------------------------------------------------------- #


@pytest.mark.loyalty
class TestCustomerDashboard:
    """Tests for GET /api/loyalty/customers/<id>/dashboard"""

    def test_get_dashboard_success(self, client, loyalty_fixtures):
        cust = loyalty_fixtures["customer"]
        response = client.get(f"/api/loyalty/customers/{cust.id}/dashboard")

        assert response.status_code == 200
        data = response.json

        # We gave them 150 points in fixtures
        assert data["current_total_points"] == 150
        assert data["active_programs_count"] == 1
        assert data["total_visits_all_time"] == 1

    def test_dashboard_customer_not_found(self, client):
        response = client.get("/api/loyalty/customers/999999/dashboard")
        assert response.status_code == 404


@pytest.mark.loyalty
class TestCustomerPrograms:
    """Tests for GET /api/loyalty/customers/<id>/programs"""

    def test_get_programs_success(self, client, loyalty_fixtures):
        cust = loyalty_fixtures["customer"]

        response = client.get(f"/api/loyalty/customers/{cust.id}/programs")

        assert response.status_code == 200
        data = response.json
        assert len(data) == 1

        prog = data[0]
        assert prog["salon_name"] == "Loyalty Salon"
        assert prog["current_points"] == 150
        # Check Next Reward Progress
        # Need 100, have 150. Points away should be 0 (or logic might say they have enough)
        assert prog["next_reward_progress"]["points_to_next_reward"] == 100
        assert prog["next_reward_progress"]["points_away"] == 0


@pytest.mark.loyalty
class TestLoyaltyActivity:
    """Tests for GET /api/loyalty/customers/<id>/programs/<salon_id>/activity"""

    def test_get_activity_success(self, client, loyalty_fixtures):
        cust = loyalty_fixtures["customer"]
        salon = loyalty_fixtures["salon"]

        response = client.get(
            f"/api/loyalty/customers/{cust.id}/programs/{salon.id}/activity"
        )

        assert response.status_code == 200
        data = response.json

        assert len(data) >= 1
        assert data[0]["points_change"] == 150
        assert data[0]["description"] == "INITIAL_BONUS"

    def test_get_activity_no_account(self, client, loyalty_fixtures):
        cust = loyalty_fixtures["customer"]
        # Random Salon ID where user has no account
        response = client.get(
            f"/api/loyalty/customers/{cust.id}/programs/99999/activity"
        )
        assert response.status_code == 404


@pytest.mark.loyalty
class TestRewardsRedemption:
    """Tests for GET rewards and POST redeem endpoints"""

    def test_get_available_rewards(self, client, loyalty_fixtures):
        cust = loyalty_fixtures["customer"]
        salon = loyalty_fixtures["salon"]

        response = client.get(
            f"/api/loyalty/customers/{cust.id}/programs/{salon.id}/rewards"
        )

        assert response.status_code == 200
        data = response.json
        assert len(data) == 1

        reward = data[0]
        assert reward["points_cost"] == 100
        assert reward["is_redeemable"] is True  # Have 150, need 100

    def test_redeem_reward_success(self, client, loyalty_fixtures, db_session):
        cust = loyalty_fixtures["customer"]
        salon = loyalty_fixtures["salon"]
        program = loyalty_fixtures["program"]

        # Payload
        payload = {"reward_id": f"prog_{program.id}_main_reward"}

        response = client.post(
            f"/api/loyalty/customers/{cust.id}/programs/{salon.id}/redeem", json=payload
        )

        assert response.status_code == 201
        data = response.json

        assert data["status"] == "success"
        # 150 - 100 = 50 remaining
        assert data["data"]["new_points_balance"] == 50
        assert "promo_code_generated" in data["data"]

        # Verify transaction log created
        txn = db_session.scalars(
            select(LoyaltyTransaction).where(
                LoyaltyTransaction.reason == "REDEEM_REWARD"
            )
        ).first()
        assert txn is not None
        assert txn.points_change == -100

    def test_redeem_reward_insufficient_points(
        self, client, loyalty_fixtures, db_session
    ):
        cust = loyalty_fixtures["customer"]
        salon = loyalty_fixtures["salon"]
        account = loyalty_fixtures["account"]
        program = loyalty_fixtures["program"]

        # Reduce points manually
        account.points = 10
        db_session.commit()

        payload = {"reward_id": f"prog_{program.id}_main_reward"}
        response = client.post(
            f"/api/loyalty/customers/{cust.id}/programs/{salon.id}/redeem", json=payload
        )

        assert response.status_code == 400
        assert "Not enough points" in response.json["message"]


@pytest.mark.loyalty
class TestSalonProgramManagement:
    """Tests for GET/PUT /api/loyalty/salon/<id>"""

    def test_get_salon_program(self, client, loyalty_fixtures):
        salon = loyalty_fixtures["salon"]
        response = client.get(f"/api/loyalty/salon/{salon.id}")

        assert response.status_code == 200
        data = response.json
        assert data["active"] == 1
        assert float(data["points_per_dollar"]) == 2.0

    def test_update_salon_program(self, client, loyalty_fixtures):
        salon = loyalty_fixtures["salon"]

        payload = {
            "active": 1,
            "points_per_dollar": 5.0,  # Increase rate
            "reward_description": "New Amazing Reward",
        }

        response = client.put(f"/api/loyalty/salon/{salon.id}", json=payload)

        assert response.status_code == 200
        data = response.json
        assert float(data["points_per_dollar"]) == 5.0
        assert data["reward_description"] == "New Amazing Reward"


@pytest.mark.loyalty
class TestCartIntegration:
    """Tests for Cart-related loyalty endpoints"""

    def test_check_cart_rewards(self, client, loyalty_fixtures):
        cust = loyalty_fixtures["customer"]
        salon = loyalty_fixtures["salon"]

        # We have 150 points. Reward cost 100. Reward value $10.
        # Logic: 150 // 100 = 1 chunk. 1 * $10 = $10 discount.

        payload = {"customer_id": cust.id, "salon_ids": [salon.id]}

        response = client.post("/api/loyalty/cart/check-rewards", json=payload)

        assert response.status_code == 200
        data = response.json

        salon_data = data[str(salon.id)]
        assert salon_data["total_points"] == 150
        assert salon_data["eligible_discount"] == 10.00
        assert salon_data["max_discount"] == 10.00

    def test_checkout_preview(self, client, loyalty_fixtures):
        cust = loyalty_fixtures["customer"]
        salon = loyalty_fixtures["salon"]

        # Buying $50 worth of stuff. Points per dollar = 2.0.
        # Should earn 100 points.
        payload = {
            "customer_id": cust.id,
            "cart_spending": [{"salon_id": salon.id, "amount_spent": 50.00}],
        }

        response = client.post("/api/loyalty/cart/checkout-preview", json=payload)

        assert response.status_code == 200
        data = response.json

        salon_data = data[str(salon.id)]
        assert salon_data["estimated_points_earned"] == 100
        assert (
            salon_data["eligible_discount"] == 10.00
        )  # Based on existing points (150)

    def test_apply_earned_points(self, client, loyalty_fixtures, db_session):
        cust = loyalty_fixtures["customer"]
        salon = loyalty_fixtures["salon"]
        account = loyalty_fixtures["account"]

        initial_points = account.points  # 150

        # Spend $10. Rate is 2.0. Earn 20 points.
        payload = {
            "customer_id": cust.id,
            "spending": [{"salon_id": salon.id, "amount_spent": 10.00}],
        }

        response = client.post("/api/loyalty/apply-earned-points", json=payload)
        assert response.status_code == 200

        # Verify database update
        db_session.refresh(account)
        assert account.points == initial_points + 20
