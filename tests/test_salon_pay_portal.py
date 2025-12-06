import pytest
import json
import uuid
from datetime import datetime, timedelta
from app.models import Employees, Appointment, AuthUser


@pytest.fixture
def sample_employee(db_session, sample_salon):
    """
    Creates a sample employee linked to the sample_salon.
    Requires an AuthUser and an Employee record.
    """
    unique_id = str(uuid.uuid4())[:8]
    emp_email = f"employee_{unique_id}@example.com"

    auth_user = AuthUser(
        email=emp_email,
        password_hash=b"hashed_pass",
        role="EMPLOYEE",
        firebase_uid=f"emp_uid_{unique_id}",
    )
    db_session.add(auth_user)
    db_session.flush()

    # 2. Create Employee profile
    employee = Employees(
        user_id=auth_user.id,
        salon_id=sample_salon.id,
        first_name="Jane",
        last_name="Stylist",
        phone_number="555-123-4567",
        employment_status="ACTIVE",
        employee_type="COMMISSION",
    )
    db_session.add(employee)
    db_session.commit()
    return employee


def create_appointment(db_session, employee, start_dt, duration_minutes, price):
    """Helper to create a completed appointment."""
    end_dt = start_dt + timedelta(minutes=duration_minutes)

    appt = Appointment(
        employee_id=employee.id,
        salon_id=employee.salon_id,
        start_at=start_dt,
        end_at=end_dt,
        price_at_book=price,
        status="COMPLETED",
    )
    db_session.add(appt)
    db_session.commit()
    return appt


@pytest.mark.salon_payroll
class TestSalonCurrentPeriod:

    def test_get_current_period_success(
        self, client, sample_salon, sample_employee, db_session
    ):
        """
        Test calculation of revenue and hours for the current bi-weekly period.
        """
        # Logic to find a date within the current bi-weekly period
        target_date = datetime.now().date()
        days_since_sunday = target_date.weekday() + 1
        if days_since_sunday == 7:
            days_since_sunday = 0
        current_sunday = target_date - timedelta(days=days_since_sunday)
        reference_sunday = datetime(2024, 1, 7).date()
        weeks_since = ((current_sunday - reference_sunday).days) // 7

        if weeks_since % 2 == 1:
            period_start = current_sunday - timedelta(days=7)
        else:
            period_start = current_sunday

        safe_date = datetime.combine(period_start, datetime.min.time()) + timedelta(
            days=2, hours=10
        )

        # Appt 1: $100, 60 mins
        create_appointment(db_session, sample_employee, safe_date, 60, 100.00)
        # Appt 2: $50, 30 mins
        create_appointment(
            db_session, sample_employee, safe_date + timedelta(hours=2), 30, 50.00
        )

        response = client.get(f"/api/salon_payroll/{sample_salon.id}/current-period")

        assert response.status_code == 200
        data = json.loads(response.data)

        # Expected: 150 revenue, 1.5 hours
        assert data["salon_id"] == sample_salon.id
        assert data["appointments_completed"] == 2
        assert data["total_service_revenue"] == 150.00
        assert data["hours_worked"] == 1.5

        # Splits (70% Employee / 30% Salon)
        assert data["employee_earnings"] == 105.00
        assert data["salon_share"] == 45.00

    def test_current_period_empty(self, client, sample_salon):
        """Test response when no appointments exist in period."""
        response = client.get(f"/api/salon_payroll/{sample_salon.id}/current-period")

        assert response.status_code == 200
        data = json.loads(response.data)

        assert data["appointments_completed"] == 0
        assert data["total_service_revenue"] == 0.0

    def test_current_period_salon_not_found(self, client):
        """Test error when salon ID does not exist."""
        response = client.get("/api/salon_payroll/99999/current-period")
        assert response.status_code == 404


@pytest.mark.salon_payroll
class TestSalonHistory:
    """Test suite for /api/salon_payroll/<salon_id>/history"""

    def test_history_aggregation(
        self, client, sample_salon, sample_employee, db_session
    ):
        """Test that history returns 6 periods and correctly aggregates past data."""
        # Create an appointment 3 weeks ago
        past_date = datetime.now() - timedelta(weeks=3)
        create_appointment(db_session, sample_employee, past_date, 60, 200.00)

        response = client.get(f"/api/salon_payroll/{sample_salon.id}/history")

        assert response.status_code == 200
        data = json.loads(response.data)

        assert len(data["history"]) == 6

        # Find the period with data
        period_with_data = next(
            (p for p in data["history"] if p["appointments_completed"] > 0), None
        )
        assert period_with_data is not None
        assert period_with_data["total_service_revenue"] == 200.00


@pytest.mark.salon_payroll
class TestSalonMonthlyTotal:
    """Test suite for /api/salon_payroll/<salon_id>/monthly-total"""

    def test_monthly_total_success(
        self, client, sample_salon, sample_employee, db_session
    ):
        """Test aggregation for the current month."""
        now = datetime.now()

        start_of_month = datetime(now.year, now.month, 1, 10, 0, 0)
        create_appointment(db_session, sample_employee, start_of_month, 120, 300.00)

        if now.month == 1:
            last_month = datetime(now.year - 1, 12, 28)
        else:
            last_month = datetime(now.year, now.month - 1, 28)

        create_appointment(db_session, sample_employee, last_month, 60, 100.00)

        response = client.get(f"/api/salon_payroll/{sample_salon.id}/monthly-total")

        assert response.status_code == 200
        data = json.loads(response.data)

        assert data["month"] == now.strftime("%B %Y")
        assert data["total_service_revenue"] == 300.00
