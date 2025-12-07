import pytest

import uuid
from datetime import datetime, timedelta, date, time
from app.models import (
    AuthUser,
    Customers,
    Salon,
    SalonOwners,
    SalonVerify,
    Employees,
    EmpAvail,
    Service,
    Appointment,
)


@pytest.fixture
def booking_fixtures(db_session):
    """
    Sets up a complete salon ecosystem for booking tests:
    - 1 Salon Owner
    - 1 Salon (Verified)
    - 1 Employee (Stylist) with Availability
    - 1 Customer
    - 1 Service (Haircut)
    """
    # 1. Salon Owner & Salon
    uid = str(uuid.uuid4())[:8]
    owner_user = AuthUser(
        email=f"book_owner_{uid}@example.com",
        password_hash=b"pass",
        role="OWNER",
        firebase_uid=f"uid_bo_{uid}",
    )
    db_session.add(owner_user)
    db_session.flush()

    owner = SalonOwners(user_id=owner_user.id, first_name="Book", last_name="Owner")
    db_session.add(owner)
    db_session.flush()

    salon = Salon(
        salon_owner_id=owner.id,
        name="Booking Salon",
        city="Book City",
        latitude=40.0,
        longitude=-74.0,
        phone="555-BOOK",
    )
    db_session.add(salon)
    db_session.flush()

    db_session.add(SalonVerify(salon_id=salon.id, status="APPROVED"))

    # 2. Employee (Stylist)
    emp_uid = str(uuid.uuid4())[:8]
    emp_user = AuthUser(
        email=f"stylist_{emp_uid}@example.com",
        password_hash=b"pass",
        role="EMPLOYEE",
        firebase_uid=f"uid_emp_{emp_uid}",
    )
    db_session.add(emp_user)
    db_session.flush()

    employee = Employees(
        user_id=emp_user.id,
        salon_id=salon.id,
        first_name="Jane",
        last_name="Stylist",
        phone_number="555-HAIR",
        employment_status="ACTIVE",
    )
    db_session.add(employee)
    db_session.flush()

    # 3. Employee Availability (Mon-Fri, 9am-5pm)
    # Note: 0=Monday, 6=Sunday in Python weekday(), but logic might vary.
    # Usually standard is Mon=0. Let's set availability for ALL days to be safe for tests.
    for i in range(7):
        avail = EmpAvail(
            employee_id=employee.id,
            weekday=i,
            start_time=time(9, 0),
            end_time=time(17, 0),
            effective_from=date(2024, 1, 1),
            effective_to=None,
        )
        db_session.add(avail)

    # 4. Service
    service = Service(
        salon_id=salon.id,
        name="Test Haircut",
        price=50.00,
        duration=60,
        is_active=True,
    )
    db_session.add(service)
    db_session.flush()

    # 5. Customer
    cust_uid = str(uuid.uuid4())[:8]
    cust_user = AuthUser(
        email=f"book_cust_{cust_uid}@example.com",
        password_hash=b"pass",
        role="CUSTOMER",
        firebase_uid=f"uid_cust_{cust_uid}",
    )
    db_session.add(cust_user)
    db_session.flush()

    customer = Customers(user_id=cust_user.id, first_name="Book", last_name="Client")
    db_session.add(customer)

    db_session.commit()

    return {
        "salon": salon,
        "employee": employee,
        "customer": customer,
        "service": service,
    }


@pytest.mark.booking
class TestSalonInfo:
    """Tests for fetching salon hours and employees."""

    def test_get_salon_hours(self, client, booking_fixtures):
        salon = booking_fixtures["salon"]
        response = client.get(f"/api/appointments/{salon.id}/hours")
        assert response.status_code == 200
        data = response.json
        assert isinstance(data, list)

    def test_get_salon_employees(self, client, booking_fixtures):
        salon = booking_fixtures["salon"]
        employee = booking_fixtures["employee"]

        response = client.get(f"/api/appointments/{salon.id}/employees")
        assert response.status_code == 200
        data = response.json

        assert len(data) >= 1
        emp_data = next((e for e in data if e["id"] == employee.id), None)
        assert emp_data is not None
        assert emp_data["first_name"] == "Jane"


@pytest.mark.booking
class TestEmployeeAvailability:
    """Tests for employee availability and time slot calculation."""

    def test_get_availability_config(self, client, booking_fixtures):
        """GET /<id>/availability"""
        employee = booking_fixtures["employee"]
        response = client.get(f"/api/appointments/{employee.id}/availability")

        assert response.status_code == 200
        data = response.json
        assert len(data) == 7
        assert data[0]["start_time"] == "09:00:00"

    def test_calculate_available_times(self, client, booking_fixtures):
        """GET /<id>/available-times"""
        employee = booking_fixtures["employee"]

        target_date = date(2025, 6, 1)  # A Sunday

        response = client.get(
            f"/api/appointments/{employee.id}/available-times",
            query_string={"date": target_date.isoformat(), "duration": 60},
        )

        assert response.status_code == 200
        slots = response.json

        assert "09:00:00" in slots
        assert "16:00:00" in slots
        assert "16:15:00" not in slots


@pytest.mark.booking
class TestCustomerAppointments:
    """Tests for fetching upcoming/previous appointments."""

    def test_upcoming_appointments(self, client, booking_fixtures, db_session):
        customer = booking_fixtures["customer"]
        salon = booking_fixtures["salon"]
        employee = booking_fixtures["employee"]
        service = booking_fixtures["service"]

        # Create future appointment
        future_appt = Appointment(
            customer_id=customer.id,
            salon_id=salon.id,
            employee_id=employee.id,
            service_id=service.id,
            start_at=datetime.now() + timedelta(days=5),
            end_at=datetime.now() + timedelta(days=5, hours=1),
            status="BOOKED",
        )
        db_session.add(future_appt)
        db_session.commit()

        response = client.get(f"/api/appointments/{customer.id}/upcoming")
        assert response.status_code == 200
        data = response.json
        assert len(data) == 1
        assert data[0]["id"] == future_appt.id

    def test_previous_appointments(self, client, booking_fixtures, db_session):
        customer = booking_fixtures["customer"]
        salon = booking_fixtures["salon"]
        service = booking_fixtures["service"]

        past_appt = Appointment(
            customer_id=customer.id,
            salon_id=salon.id,
            service_id=service.id,
            start_at=datetime.now() - timedelta(days=5),
            end_at=datetime.now() - timedelta(days=5, hours=1),
            status="COMPLETED",
        )
        db_session.add(past_appt)
        db_session.commit()

        response = client.get(f"/api/appointments/{customer.id}/previous")
        assert response.status_code == 200
        data = response.json
        assert len(data) == 1
        assert data[0]["id"] == past_appt.id


@pytest.mark.booking
class TestBookingOperations:
    """Tests for creating (booking) and editing appointments."""

    def test_add_appointment_success(self, client, booking_fixtures):
        """Test POST /add"""
        customer = booking_fixtures["customer"]
        salon = booking_fixtures["salon"]
        service = booking_fixtures["service"]
        employee = booking_fixtures["employee"]

        start_dt = (datetime.now() + timedelta(days=1)).replace(microsecond=0)

        payload = {
            "customer_id": customer.id,
            "salon_id": salon.id,
            "service_id": service.id,
            "employee_id": employee.id,
            "start_at": start_dt.isoformat(),
            "notes": "First time booking",
            "pictures": ["http://ref.com/style.jpg"],
        }

        response = client.post("/api/appointments/add", json=payload)

        assert response.status_code == 201
        data = response.json
        assert data["message"] == "Appointment created successfully"
        assert data["photos_count"] == 1

        assert data["start_at"].replace("T", " ") == str(start_dt)

    def test_edit_appointment(self, client, booking_fixtures, db_session):
        """Test PUT /<id>/appointments/<id>"""
        customer = booking_fixtures["customer"]
        salon = booking_fixtures["salon"]
        service = booking_fixtures["service"]

        # 1. Create Appointment
        appt = Appointment(
            customer_id=customer.id,
            salon_id=salon.id,
            service_id=service.id,
            start_at=datetime.now() + timedelta(days=2),
            end_at=datetime.now() + timedelta(days=2, hours=1),
            status="BOOKED",
        )
        db_session.add(appt)
        db_session.commit()

        # 2. Edit it (Cancel)
        payload = {"status": "CANCELLED", "notes": "Something came up"}

        response = client.put(
            f"/api/appointments/{customer.id}/appointments/{appt.id}", json=payload
        )

        assert response.status_code == 200
        data = response.json
        assert data["status"] == "CANCELLED"
        assert data["notes"] == "Something came up"

    def test_edit_appointment_forbidden(self, client, booking_fixtures, db_session):
        """Test editing someone else's appointment."""
        customer = booking_fixtures["customer"]
        salon = booking_fixtures["salon"]
        service = booking_fixtures["service"]

        # Create appointment for this customer
        appt = Appointment(
            customer_id=customer.id,
            salon_id=salon.id,
            service_id=service.id,
            start_at=datetime.now(),
            end_at=datetime.now(),
            status="BOOKED",
        )
        db_session.add(appt)
        db_session.commit()

        wrong_id = customer.id + 999
        response = client.put(
            f"/api/appointments/{wrong_id}/appointments/{appt.id}",
            json={"status": "CANCELLED"},
        )

        assert response.status_code == 404
