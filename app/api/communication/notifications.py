from flask import Blueprint, request, jsonify
from app.services.email_service import email_service
from app.extensions import db
from app.models import Appointment, Customers, Employees, Salon, Service, AuthUser
from datetime import datetime
from urllib.parse import quote

notifications_bp = Blueprint("notifications", __name__, url_prefix="/api/notifications")


@notifications_bp.route("/test", methods=["POST"])
def test_email():
    """
    Test email configuration
    ---
    tags:
      - Notifications
    summary: Send a test email to verify Resend integration
    description: Sends a test email to the provided address to verify that the email service is configured correctly
    parameters:
      - in: body
        name: body
        required: true
        description: Email address to send test to
        schema:
          type: object
          required:
            - email
          properties:
            email:
              type: string
              format: email
              example: test@example.com
    responses:
      200:
        description: Test email sent successfully
        schema:
          type: object
          properties:
            status:
              type: string
              example: success
            message:
              type: string
              example: Test email sent to test@example.com
            email_id:
              type: string
              example: abc123xyz
      400:
        description: Invalid request - email is required
      500:
        description: Server error or email service error
    """
    try:
        data = request.get_json()
        email = data.get("email")

        if not email:
            return jsonify({"error": "Email is required"}), 400

        result = email_service.send_test_email(email)

        if result["success"]:
            return (
                jsonify(
                    {
                        "status": "success",
                        "message": result["message"],
                        "email_id": result.get("email_id"),
                    }
                ),
                200,
            )
        else:
            return jsonify({"status": "error", "error": result["error"]}), 500

    except Exception as e:
        return jsonify({"status": "error", "error": str(e)}), 500


@notifications_bp.route("/appointment/reminder", methods=["POST"])
def send_appointment_reminder():
    """
    Send appointment reminder email
    ---
    tags:
      - Notifications
    summary: Send reminder email 1 hour before appointment
    description: Sends a reminder email to the customer 1 hour before their scheduled appointment. Typically triggered by a cron job or scheduler. Includes all appointment details and a link to view the appointment.
    parameters:
      - in: body
        name: body
        required: true
        description: Appointment ID to send reminder for
        schema:
          type: object
          required:
            - appointment_id
          properties:
            appointment_id:
              type: integer
              example: 123
              description: ID of the appointment to remind about
    responses:
      200:
        description: Reminder email sent successfully
        schema:
          type: object
          properties:
            status:
              type: string
              example: success
            message:
              type: string
              example: Reminder email sent to customer@example.com
            email_id:
              type: string
              example: re_abc123xyz
      400:
        description: Invalid request - appointment_id is required or customer email not found
      404:
        description: Appointment not found
      500:
        description: Server error or email service error
    """
    try:
        data = request.get_json()
        appointment_id = data.get("appointment_id")

        if not appointment_id:
            return jsonify({"error": "appointment_id is required"}), 400

        # Fetch appointment with relationships
        appointment = db.session.query(Appointment).filter_by(id=appointment_id).first()
        if not appointment:
            return jsonify({"error": "Appointment not found"}), 404

        # Fetch customer with user relationship
        customer = (
            db.session.query(Customers).filter_by(id=appointment.customer_id).first()
        )
        if not customer:
            return jsonify({"error": "Customer not found"}), 404

        # Get email from AuthUser via user_id
        auth_user = db.session.query(AuthUser).filter_by(id=customer.user_id).first()
        if not auth_user or not auth_user.email:
            return jsonify({"error": "Customer email not found"}), 400

        # Fetch employee, salon, service
        employee = (
            db.session.query(Employees).filter_by(id=appointment.employee_id).first()
        )
        salon = db.session.query(Salon).filter_by(id=appointment.salon_id).first()

        service = None
        if appointment.service_id:
            service = (
                db.session.query(Service).filter_by(id=appointment.service_id).first()
            )

        # Format appointment date/time
        try:
            if isinstance(appointment.start_at, str):
                for fmt in ["%m/%d/%Y %H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"]:
                    try:
                        appt_datetime = datetime.strptime(appointment.start_at, fmt)
                        break
                    except ValueError:
                        continue
                else:
                    appt_datetime = datetime.now()
            else:
                appt_datetime = appointment.start_at
        except Exception as e:
            print(f"Date parsing error: {e}")
            appt_datetime = datetime.now()

        # Build customer name
        customer_name = f"{customer.first_name} {customer.last_name}".strip()
        if not customer_name:
            customer_name = "Valued Customer"

        # Send the email
        result = email_service.send_appointment_reminder(
            to_email=auth_user.email,
            customer_name=customer_name,
            salon_name=salon.name if salon else "Salon",
            service_name=service.name if service else "Service",
            appointment_date=appt_datetime.strftime("%B %d, %Y"),
            appointment_time=appt_datetime.strftime("%I:%M %p"),
            stylist_name=(
                f"{employee.first_name} {employee.last_name}"
                if employee
                else "Your Stylist"
            ),
            appointment_id=appointment.id,
            salon_address=salon.address if salon else "",
        )

        if result["success"]:
            return (
                jsonify(
                    {
                        "status": "success",
                        "message": result["message"],
                        "email_id": result.get("email_id"),
                    }
                ),
                200,
            )
        else:
            return jsonify({"status": "error", "error": result["error"]}), 500

    except Exception as e:
        import traceback

        print(f"Error in send_appointment_reminder: {traceback.format_exc()}")
        return jsonify({"status": "error", "error": str(e)}), 500


@notifications_bp.route("/appointment/cancel", methods=["POST"])
def send_cancellation_notification():
    """
    Send cancellation notification
    ---
    tags:
      - Notifications
    summary: Notify about appointment cancellation
    description: Sends a cancellation notification email to either the customer or employee depending on who cancelled. If customer cancels, employee is notified. If employee/salon cancels, customer is notified.
    parameters:
      - in: body
        name: body
        required: true
        description: Cancellation details
        schema:
          type: object
          required:
            - appointment_id
            - cancelled_by
          properties:
            appointment_id:
              type: integer
              example: 123
              description: ID of the cancelled appointment
            cancelled_by:
              type: string
              enum: [customer, employee]
              example: customer
              description: Who initiated the cancellation
            reason:
              type: string
              example: Personal emergency
              description: Optional reason for cancellation
    responses:
      200:
        description: Cancellation notification sent successfully
        schema:
          type: object
          properties:
            status:
              type: string
              example: success
            message:
              type: string
              example: Cancellation notification sent
      400:
        description: Invalid request - missing required fields or email not found
      404:
        description: Appointment or related data not found
      500:
        description: Server error or email service error
    """
    try:
        data = request.get_json()
        appointment_id = data.get("appointment_id")
        cancelled_by = data.get("cancelled_by")
        reason = data.get("reason", "")

        if not appointment_id or not cancelled_by:
            return (
                jsonify({"error": "appointment_id and cancelled_by are required"}),
                400,
            )

        # Fetch appointment
        appointment = db.session.query(Appointment).filter_by(id=appointment_id).first()
        if not appointment:
            return jsonify({"error": "Appointment not found"}), 404

        # Fetch related data
        customer = (
            db.session.query(Customers).filter_by(id=appointment.customer_id).first()
        )
        employee = (
            db.session.query(Employees).filter_by(id=appointment.employee_id).first()
        )
        salon = db.session.query(Salon).filter_by(id=appointment.salon_id).first()

        service = None
        if appointment.service_id:
            service = (
                db.session.query(Service).filter_by(id=appointment.service_id).first()
            )

        # Format date/time
        try:
            if isinstance(appointment.start_at, str):
                for fmt in ["%m/%d/%Y %H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"]:
                    try:
                        appt_datetime = datetime.strptime(appointment.start_at, fmt)
                        break
                    except ValueError:
                        continue
                else:
                    appt_datetime = datetime.now()
            else:
                appt_datetime = appointment.start_at
        except Exception:
            appt_datetime = datetime.now()

        # Determine recipient
        if cancelled_by == "customer":
            auth_employee = (
                db.session.query(AuthUser).filter_by(id=employee.user_id).first()
            )

            if not auth_employee or not auth_employee.email:
                return jsonify({"error": "Employee email not found"}), 400

            to_email = auth_employee.email
            to_name = f"{employee.first_name} {employee.last_name}"
        else:
            if not customer:
                return jsonify({"error": "Customer not found"}), 404
            auth_user = (
                db.session.query(AuthUser).filter_by(id=customer.user_id).first()
            )
            if not auth_user or not auth_user.email:
                return jsonify({"error": "Customer email not found"}), 400
            to_email = auth_user.email
            to_name = (
                f"{customer.first_name} {customer.last_name}".strip()
                or "Valued Customer"
            )

        result = email_service.send_cancellation_notification(
            to_email=to_email,
            to_name=to_name,
            cancelled_by=cancelled_by,
            salon_name=salon.name if salon else "Salon",
            service_name=service.name if service else "Service",
            appointment_date=appt_datetime.strftime("%B %d, %Y"),
            appointment_time=appt_datetime.strftime("%I:%M %p"),
            salon_id=salon.id if salon else 0,
            cancellation_reason=reason,
        )

        if result["success"]:
            return jsonify({"status": "success", "message": result["message"]}), 200
        else:
            return jsonify({"status": "error", "error": result["error"]}), 500

    except Exception as e:
        import traceback

        print(f"Error in send_cancellation_notification: {traceback.format_exc()}")
        return jsonify({"status": "error", "error": str(e)}), 500


@notifications_bp.route("/appointment/message", methods=["POST"])
def send_appointment_message():
    """
    Send appointment message
    ---
    tags:
      - Notifications
    summary: Send a message between customer and employee
    description: Facilitates communication between customer and employee via email with a 'Reply via Email' button.
    parameters:
      - in: body
        name: body
        required: true
        schema:
          type: object
          required:
            - appointment_id
            - from_user_type
            - message
          properties:
            appointment_id:
              type: integer
            from_user_type:
              type: string
              enum: [customer, employee]
            message:
              type: string
    responses:
      200:
        description: Message sent successfully
      400:
        description: Invalid request or missing emails
      404:
        description: Appointment not found
      500:
        description: Server error
    """
    try:
        data = request.get_json()
        appointment_id = data.get("appointment_id")
        from_user_type = data.get("from_user_type")
        message_text = data.get("message")

        # 1. Validation
        if not all([appointment_id, from_user_type, message_text]):
            return (
                jsonify(
                    {
                        "error": "appointment_id, from_user_type, and message are required"
                    }
                ),
                400,
            )

        # 2. Fetch Appointment
        appointment = db.session.query(Appointment).filter_by(id=appointment_id).first()
        if not appointment:
            return jsonify({"error": "Appointment not found"}), 404

        # 3. Fetch Related Entities
        customer = (
            db.session.query(Customers).filter_by(id=appointment.customer_id).first()
        )
        employee = (
            db.session.query(Employees).filter_by(id=appointment.employee_id).first()
        )
        salon = db.session.query(Salon).filter_by(id=appointment.salon_id).first()

        service = None
        if appointment.service_id:
            service = (
                db.session.query(Service).filter_by(id=appointment.service_id).first()
            )

        # 4. Parse Date
        try:
            if isinstance(appointment.start_at, str):
                for fmt in ["%m/%d/%Y %H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"]:
                    try:
                        appt_datetime = datetime.strptime(appointment.start_at, fmt)
                        break
                    except ValueError:
                        continue
                else:
                    appt_datetime = datetime.now()
            else:
                appt_datetime = appointment.start_at
        except Exception:
            appt_datetime = datetime.now()

        # 5. Fetch Emails
        if not customer:
            return jsonify({"error": "Customer not found"}), 404
        cust_auth = db.session.query(AuthUser).filter_by(id=customer.user_id).first()
        customer_email = cust_auth.email if cust_auth else None

        if not employee:
            return jsonify({"error": "Employee not found"}), 404
        emp_auth = db.session.query(AuthUser).filter_by(id=employee.user_id).first()
        employee_email = emp_auth.email if emp_auth else None

        if not customer_email or not employee_email:
            return (
                jsonify({"error": "Missing email address for customer or employee"}),
                400,
            )

        if from_user_type == "customer":

            to_email = employee_email
            to_name = f"{employee.first_name} {employee.last_name}"
            from_name = f"{customer.first_name} {customer.last_name}"

            reply_target_email = customer_email

        else:

            to_email = customer_email
            to_name = f"{customer.first_name} {customer.last_name}"
            from_name = f"{employee.first_name} {employee.last_name}"

            reply_target_email = employee_email

        # 7. Generate Mailto Link
        subject_line = quote(f"Re: Appointment at {salon.name}")
        mailto_link = f"mailto:{reply_target_email}?subject={subject_line}"

        # 8. Send Email
        result = email_service.send_appointment_message(
            to_email=to_email,
            to_name=to_name,
            from_name=from_name,
            message_text=message_text,
            salon_name=salon.name if salon else "Salon",
            service_name=service.name if service else "Service",
            appointment_date=appt_datetime.strftime("%B %d, %Y"),
            appointment_time=appt_datetime.strftime("%I:%M %p"),
            appointment_id=appointment.id,
            mailto_link=mailto_link,
        )

        if result["success"]:
            return jsonify({"status": "success", "message": result["message"]}), 200
        else:
            return jsonify({"status": "error", "error": result["error"]}), 500

    except Exception as e:
        return jsonify({"status": "error", "error": str(e)}), 500


@notifications_bp.route("/review-request", methods=["POST"])
def send_review_request():
    """
    Send review request email
    ---
    tags:
      - Notifications
    summary: Request customer review after appointment
    description: Sends a review request email directing the customer to the website landing page.
    parameters:
      - in: body
        name: body
        required: true
        schema:
          type: object
          required:
            - customer_id
            - salon_id
          properties:
            customer_id:
              type: integer
            salon_id:
              type: integer
            service_name:
              type: string
    responses:
      200:
        description: Review request sent successfully
    """
    try:
        data = request.get_json()
        customer_id = data.get("customer_id")
        salon_id = data.get("salon_id")
        service_name = data.get("service_name", "Service")

        if not customer_id or not salon_id:
            return jsonify({"error": "customer_id and salon_id are required"}), 400

        # Get customer and salon
        customer = db.session.query(Customers).filter_by(id=customer_id).first()
        salon = db.session.query(Salon).filter_by(id=salon_id).first()

        if not customer:
            return jsonify({"error": "Customer not found"}), 404
        if not salon:
            return jsonify({"error": "Salon not found"}), 404

        # Get email from AuthUser
        auth_user = db.session.query(AuthUser).filter_by(id=customer.user_id).first()
        if not auth_user or not auth_user.email:
            return jsonify({"error": "Customer email not found"}), 400

        customer_name = (
            f"{customer.first_name} {customer.last_name}".strip() or "Valued Customer"
        )

        result = email_service.send_review_request(
            to_email=auth_user.email,
            customer_name=customer_name,
            salon_name=salon.name,
            salon_id=salon.id,
            service_name=service_name,
        )

        if result["success"]:
            return jsonify({"status": "success", "message": result["message"]}), 200
        else:
            return jsonify({"status": "error", "error": result["error"]}), 500

    except Exception as e:
        db.session.rollback()
        return jsonify({"status": "error", "error": str(e)}), 500


@notifications_bp.route("/hours-change", methods=["POST"])
def send_hours_change():
    """
    Notify employees about hours change
    ---
    tags:
      - Notifications
    summary: Bulk notify employees about schedule changes
    description: Sends a notification email to all active employees of a salon when the business hours are changed. Useful for keeping staff informed about schedule updates.
    parameters:
      - in: body
        name: body
        required: true
        description: New hours schedule
        schema:
          type: object
          required:
            - salon_id
            - new_hours
          properties:
            salon_id:
              type: integer
              example: 123
              description: ID of the salon with updated hours
            new_hours:
              type: object
              example:
                Monday: 9AM-5PM
                Tuesday: 9AM-5PM
                Wednesday: 9AM-6PM
                Thursday: 9AM-6PM
                Friday: 9AM-7PM
                Saturday: 10AM-4PM
                Sunday: Closed
              description: Object containing new hours for each day of the week
    responses:
      200:
        description: Hours change notification sent to all employees
        schema:
          type: object
          properties:
            status:
              type: string
              example: success
            message:
              type: string
              example: Hours change notification sent to 5 employees
            sent_count:
              type: integer
              example: 5
              description: Number of employees successfully notified
            total_count:
              type: integer
              example: 5
              description: Total number of employees attempted
      400:
        description: Invalid request - missing required fields
      404:
        description: Salon not found or no active employees found
      500:
        description: Server error or email service error
    """
    try:
        data = request.get_json()
        salon_id = data.get("salon_id")
        new_hours = data.get("new_hours")

        if not salon_id or not new_hours:
            return jsonify({"error": "salon_id and new_hours are required"}), 400

        # Get salon and employees
        salon = db.session.query(Salon).filter_by(id=salon_id).first()
        if not salon:
            return jsonify({"error": "Salon not found"}), 404

        employees = (
            db.session.query(Employees)
            .filter_by(salon_id=salon_id, employment_status="active")
            .all()
        )

        if not employees:
            return jsonify({"error": "No active employees found"}), 404

        employee_emails = [emp.email for emp in employees if emp.email]

        if not employee_emails:
            return jsonify({"error": "No employee emails found"}), 400

        result = email_service.send_hours_change_notification(
            to_emails=employee_emails, salon_name=salon.name, new_hours=new_hours
        )

        if result["success"]:
            return (
                jsonify(
                    {
                        "status": "success",
                        "message": result["message"],
                        "sent_count": result.get("success_count"),
                        "total_count": result.get("total_count"),
                    }
                ),
                200,
            )
        else:
            return jsonify({"status": "error", "error": result["error"]}), 500

    except Exception as e:
        import traceback

        print(f"Error in send_hours_change: {traceback.format_exc()}")
        return jsonify({"status": "error", "error": str(e)}), 500
