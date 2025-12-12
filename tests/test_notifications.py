import pytest
import json
import uuid
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta, timezone
from app.models import Salon, Service, Appointment, Customers, Employees, AuthUser, SalonOwners


@pytest.fixture
def notification_data(db_session):
    """
    Creates a full ecosystem:
    1. Owner -> Salon
    2. Service
    3. Employee (AuthUser + Employee profile)
    4. Customer (AuthUser + Customer profile)
    5. Appointment linking them all
    """
    unique_id = str(uuid.uuid4())[:8]

    # 1. Owner & Salon
    owner_user = AuthUser(
        email=f"owner_{unique_id}@test.com", 
        password_hash=b"x", 
        role="OWNER", 
        firebase_uid=f"uid_o_{unique_id}"
    )
    db_session.add(owner_user)
    db_session.flush()

    owner = SalonOwners(user_id=owner_user.id, first_name="Owner", last_name="Boss")
    db_session.add(owner)
    db_session.flush()

    salon = Salon(
        salon_owner_id=owner.id,
        name=f"Notify Salon {unique_id}",
        address="123 Notify St",
        city="Email City",
        latitude=40.0,
        longitude=-74.0,
        phone="555-0000"
    )
    db_session.add(salon)
    db_session.flush()

    # 2. Service
    service = Service(
        salon_id=salon.id,
        name="Haircut",
        price=50.00,
        duration=60
    )
    db_session.add(service)
    db_session.flush()

    # 3. Employee
    emp_user = AuthUser(
        email=f"emp_{unique_id}@test.com", 
        password_hash=b"x", 
        role="EMPLOYEE", 
        firebase_uid=f"uid_e_{unique_id}"
    )
    db_session.add(emp_user)
    db_session.flush()

    employee = Employees(
        user_id=emp_user.id,
        salon_id=salon.id,
        first_name="Stylist",
        last_name="Sue",
        employment_status="active"  
    )
    db_session.add(employee)
    db_session.flush()

    # 4. Customer
    cust_user = AuthUser(
        email=f"cust_{unique_id}@test.com", 
        password_hash=b"x", 
        role="CUSTOMER", 
        firebase_uid=f"uid_c_{unique_id}"
    )
    db_session.add(cust_user)
    db_session.flush()

    customer = Customers(
        user_id=cust_user.id,
        first_name="John",
        last_name="Doe",
        phone_number="555-9999"
    )
    db_session.add(customer)
    db_session.flush()

    start_time = datetime.now(timezone.utc).replace(microsecond=0) + timedelta(days=1)
    
    appointment = Appointment(
        salon_id=salon.id,
        customer_id=customer.id,
        employee_id=employee.id,
        service_id=service.id,
        start_at=start_time,
        end_at=start_time + timedelta(minutes=60),
        status="SCHEDULED",
        price_at_book=50.00
    )
    db_session.add(appointment)
    db_session.commit()

    return {
        "salon_id": salon.id,
        "customer_id": customer.id,
        "employee_id": employee.id,
        "appointment_id": appointment.id,
        "customer_email": cust_user.email,
        "employee_email": emp_user.email
    }



@patch("app.api.communication.notifications.email_service")
class TestNotifications:

    def test_send_test_email_success(self, mock_email, client):
        """Test the simple test email endpoint."""
        # Setup mock return
        mock_email.send_test_email.return_value = {
            "success": True, 
            "message": "Sent", 
            "email_id": "123"
        }

        response = client.post("/api/notifications/test", json={"email": "test@test.com"})
        
        assert response.status_code == 200
        assert response.json["status"] == "success"
        mock_email.send_test_email.assert_called_once_with("test@test.com")

    def test_send_test_email_missing_field(self, mock_email, client):
        """Test error when email is missing."""
        response = client.post("/api/notifications/test", json={})
        assert response.status_code == 400
        assert "Email is required" in response.json["error"]

    def test_appointment_reminder_success(self, mock_email, client, notification_data):
        """Test sending an appointment reminder."""
        mock_email.send_appointment_reminder.return_value = {"success": True, "message": "OK"}

        payload = {"appointment_id": notification_data["appointment_id"]}
        response = client.post("/api/notifications/appointment/reminder", json=payload)

        assert response.status_code == 200
        assert response.json["status"] == "success"
        
        # Verify correct email was used
        args, kwargs = mock_email.send_appointment_reminder.call_args
        assert kwargs["to_email"] == notification_data["customer_email"]
        assert kwargs["customer_name"] == "John Doe"

    def test_appointment_reminder_not_found(self, mock_email, client):
        """Test reminder for non-existent appointment."""
        response = client.post("/api/notifications/appointment/reminder", json={"appointment_id": 99999})
        assert response.status_code == 404
        assert "Appointment not found" in response.json["error"]

    def test_cancellation_by_customer(self, mock_email, client, notification_data):
        """Test cancellation notification when customer cancels (notifies employee)."""
        mock_email.send_cancellation_notification.return_value = {"success": True, "message": "OK"}

        payload = {
            "appointment_id": notification_data["appointment_id"],
            "cancelled_by": "customer",
            "reason": "Changed mind"
        }
        response = client.post("/api/notifications/appointment/cancel", json=payload)

        assert response.status_code == 200
        
        # Should email the EMPLOYEE
        args, kwargs = mock_email.send_cancellation_notification.call_args
        assert kwargs["to_email"] == notification_data["employee_email"]
        assert kwargs["cancelled_by"] == "customer"

    def test_cancellation_by_employee(self, mock_email, client, notification_data):
        """Test cancellation notification when employee cancels (notifies customer)."""
        mock_email.send_cancellation_notification.return_value = {"success": True, "message": "OK"}

        payload = {
            "appointment_id": notification_data["appointment_id"],
            "cancelled_by": "employee",
            "reason": "Sick day"
        }
        response = client.post("/api/notifications/appointment/cancel", json=payload)

        assert response.status_code == 200
        
        # Should email the CUSTOMER
        args, kwargs = mock_email.send_cancellation_notification.call_args
        assert kwargs["to_email"] == notification_data["customer_email"]
        assert kwargs["cancelled_by"] == "employee"

    def test_appointment_message_customer_to_employee(self, mock_email, client, notification_data):
        """Test messaging: Customer -> Employee."""
        mock_email.send_appointment_message.return_value = {"success": True, "message": "OK"}

        payload = {
            "appointment_id": notification_data["appointment_id"],
            "from_user_type": "customer",
            "message": "Running late!"
        }
        response = client.post("/api/notifications/appointment/message", json=payload)

        assert response.status_code == 200
        
        # Target should be Employee
        args, kwargs = mock_email.send_appointment_message.call_args
        assert kwargs["to_email"] == notification_data["employee_email"]
        assert "Running late!" in kwargs["message_text"]

    def test_appointment_message_employee_to_customer(self, mock_email, client, notification_data):
        """Test messaging: Employee -> Customer."""
        mock_email.send_appointment_message.return_value = {"success": True, "message": "OK"}

        payload = {
            "appointment_id": notification_data["appointment_id"],
            "from_user_type": "employee",
            "message": "Where are you?"
        }
        response = client.post("/api/notifications/appointment/message", json=payload)

        assert response.status_code == 200
        
        # Target should be Customer
        args, kwargs = mock_email.send_appointment_message.call_args
        assert kwargs["to_email"] == notification_data["customer_email"]

    def test_review_request_success(self, mock_email, client, notification_data):
        """Test sending a review request."""
        mock_email.send_review_request.return_value = {"success": True, "message": "OK"}

        payload = {
            "customer_id": notification_data["customer_id"],
            "salon_id": notification_data["salon_id"],
            "service_name": "Haircut"
        }
        response = client.post("/api/notifications/review-request", json=payload)

        assert response.status_code == 200
        
        args, kwargs = mock_email.send_review_request.call_args
        assert kwargs["to_email"] == notification_data["customer_email"]

    def test_hours_change_success(self, mock_email, client, notification_data):
        """Test bulk hours change notification."""
        mock_email.send_hours_change_notification.return_value = {
            "success": True, 
            "message": "OK",
            "success_count": 1,
            "total_count": 1
        }

        payload = {
            "salon_id": notification_data["salon_id"],
            "new_hours": {"Monday": "10-6"}
        }
        response = client.post("/api/notifications/hours-change", json=payload)

        assert response.status_code == 200
        assert response.json["sent_count"] == 1
        
        args, kwargs = mock_email.send_hours_change_notification.call_args
        assert notification_data["employee_email"] in kwargs["to_emails"]

    def test_hours_change_no_employees(self, mock_email, client):
        response = client.post("/api/notifications/hours-change", json={
            "salon_id": 99999,
            "new_hours": {"Monday": "Closed"} 
        })
        assert response.status_code == 404
        assert "Salon not found" in response.json["error"]