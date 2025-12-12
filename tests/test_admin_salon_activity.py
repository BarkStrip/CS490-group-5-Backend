import pytest
import json
import uuid
from datetime import datetime, timedelta, time, timezone
from app.models import Salon, SalonVerify, Appointment, Customers, AuthUser

# -------------------------------------------------------------------
# Fixtures specific to this test file
# -------------------------------------------------------------------

@pytest.fixture
def activity_data(db_session, sample_owner):
    """
    Populates the DB with:
    1. A Pending Salon (for /pending)
    2. A Top Salon with Appointments (for /top and /trends)
    3. Completed Appointments (for /metrics and /wait-time)
    4. Past Customers/Salons (for trends)
    """
    
    unique_id = str(uuid.uuid4())[:8]
    
    def utc_now_naive():
        return datetime.now(timezone.utc).replace(tzinfo=None)

    pending_salon = Salon(
        salon_owner_id=sample_owner.id,
        name=f"Pending Salon {unique_id}",
        address="456 Pending St",
        city="Jersey City",
        phone="555-0000",
        latitude=40.0,
        longitude=-74.0,
        created_at=utc_now_naive()
    )
    db_session.add(pending_salon)
    db_session.flush()
    
    pending_verify = SalonVerify(
        salon_id=pending_salon.id, 
        status="PENDING"
    )
    db_session.add(pending_verify)

    # --- 2. Active Salon (for appointments) ---
    active_salon = Salon(
        salon_owner_id=sample_owner.id,
        name=f"Top Rated Salon {unique_id}",
        address="789 Active Ave",
        city="Hoboken",
        phone="555-1111",
        latitude=40.1,
        longitude=-74.1,
        created_at=utc_now_naive() - timedelta(days=5)
    )
    db_session.add(active_salon)
    db_session.flush()

    # --- 3. Appointments ---
    # Using 'price_at_book' as per your models.py
    
    today = utc_now_naive().date()
    # Ensure times are simple (10:00 AM)
    start_time = datetime.combine(today, time(10, 0)) 
    
    appt1 = Appointment(
        salon_id=active_salon.id,
        status="COMPLETED",
        created_at=start_time - timedelta(minutes=120),
        start_at=start_time,
        end_at=start_time + timedelta(minutes=60),
        price_at_book=50.0 
    )
    
    appt2 = Appointment(
        salon_id=active_salon.id,
        status="COMPLETED",
        created_at=start_time - timedelta(days=1),
        start_at=start_time + timedelta(hours=2),
        end_at=start_time + timedelta(hours=2, minutes=30),
        price_at_book=30.0 
    )

    appt3 = Appointment(
        salon_id=active_salon.id,
        status="SCHEDULED",
        created_at=utc_now_naive(),
        start_at=utc_now_naive() + timedelta(days=1),
        end_at=utc_now_naive() + timedelta(days=1, hours=1),
        price_at_book=40.0
    )
    
    db_session.add_all([appt1, appt2, appt3])

    # --- 4. Customers (for trends) ---
    # Use unique emails and UIDs
    email1 = f"trend1_{unique_id}@test.com"
    email2 = f"trend2_{unique_id}@test.com"
    uid1 = f"uid_t1_{unique_id}"
    uid2 = f"uid_t2_{unique_id}"

    auth_c1 = AuthUser(email=email1, password_hash=b"x", role="CUSTOMER", firebase_uid=uid1)
    auth_c2 = AuthUser(email=email2, password_hash=b"x", role="CUSTOMER", firebase_uid=uid2)
    db_session.add_all([auth_c1, auth_c2])
    db_session.flush()

    cust1 = Customers(user_id=auth_c1.id, first_name="Trend", last_name="One", created_at=utc_now_naive())
    cust2 = Customers(user_id=auth_c2.id, first_name="Trend", last_name="Two", created_at=utc_now_naive() - timedelta(days=2))
    db_session.add_all([cust1, cust2])

    db_session.commit()

    return {
        "pending_salon_id": pending_salon.id,
        "active_salon_id": active_salon.id,
        "active_salon_name": active_salon.name,
        "appt1_id": appt1.id
    }


# -------------------------------------------------------------------
# Test Class
# -------------------------------------------------------------------

@pytest.mark.admin
class TestAdminSalonActivity:
    
    def test_get_pending_verifications(self, client, activity_data):
        response = client.get("/api/admin/salon-activity/pending")
        
        assert response.status_code == 200
        data = json.loads(response.data)
        
        assert "pending" in data
        pending_list = data["pending"]
        assert len(pending_list) >= 1
        
        found = any(item['salon_id'] == activity_data['pending_salon_id'] for item in pending_list)
        assert found, "Created pending salon not found in response"

    def test_get_top_salons(self, client, activity_data):
        """Test retrieving top salons by appointment count."""
        response = client.get("/api/admin/salon-activity/top")
        
        assert response.status_code == 200
        data = json.loads(response.data)
        
        assert "top_salons" in data
        # Check for the dynamic name we created
        target_name = activity_data['active_salon_name']
        top_salon = next((s for s in data["top_salons"] if s["name"] == target_name), None)
        assert top_salon is not None
        assert top_salon["count"] == 3

    def test_get_appointment_trends(self, client, activity_data):
        """Test appointment trends (counts per day)."""
        response = client.get("/api/admin/salon-activity/trends")
        assert response.status_code == 200
        data = json.loads(response.data)
        
        assert "trends" in data
        assert len(data["trends"]) >= 7
        
        # Use timezone-aware UTC for today string
        today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        url = f"/api/admin/salon-activity/trends?from={today_str}&to={today_str}"
        response_filtered = client.get(url)
        assert response_filtered.status_code == 200
        data_filtered = json.loads(response_filtered.data)
        
        today_entry = next((d for d in data_filtered["trends"] if d["day"] == today_str), None)
        assert today_entry is not None

    def test_get_appointment_metrics(self, client, activity_data):
        """Test average duration metrics."""
        response = client.get("/api/admin/salon-activity/metrics")
        
        assert response.status_code == 200
        data = json.loads(response.data)
        
        assert "avg_time" in data
        # We have two completed appts: 60 mins and 30 mins. Avg should be 45.0
        assert data["avg_time"] == 45.0

    def test_customers_trend(self, client, activity_data):
        """Test new customers trend."""
        response = client.get("/api/admin/salon-activity/customers-trend")
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert "customers" in data
        
        days_with_data = [d for d in data["customers"] if d["count"] > 0]
        assert len(days_with_data) >= 1

    def test_salons_trend(self, client, activity_data):
        """Test new salons trend."""
        response = client.get("/api/admin/salon-activity/salons-trend")
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert "salons" in data
        
        days_with_data = [d for d in data["salons"] if d["count"] > 0]
        assert len(days_with_data) >= 1

    def test_get_peak_hours(self, client, activity_data):
        """Test peak hours analytics."""
        response = client.get("/api/admin/salon-activity/peak-hours")
        
        assert response.status_code == 200
        data = json.loads(response.data)
        
        assert "byHour" in data
        assert "byDowHour" in data
        
        hour_10 = next((h for h in data["byHour"] if h["hour"] == 10), None)
        assert hour_10 is not None
        assert hour_10["count"] >= 1

    def test_get_wait_time_metrics(self, client, activity_data):
        """Test wait time calculation."""
        response = client.get("/api/admin/salon-activity/wait-time")
        
        assert response.status_code == 200
        data = json.loads(response.data)
        
        assert "avg_wait_minutes" in data
        assert isinstance(data["avg_wait_minutes"], (int, float))
        assert data["sample_size"] > 0

    def test_salon_activity_report_pdf(self, client, activity_data):
        """Test PDF generation endpoint."""
        sid = activity_data['active_salon_id']
        response = client.get(f"/api/admin/salon-activity/report-pdf?salonId={sid}")
        
        assert response.status_code == 200
        assert response.headers["Content-Type"] == "application/pdf"
        assert b"%PDF" in response.data