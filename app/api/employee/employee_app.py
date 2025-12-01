from flask import Blueprint, jsonify, request
from app.extensions import db
from app.models import (
    Employees,
    Appointment,
    Customers,
    Salon,
    Service,
    Message,
    AppointmentImage,
)
from sqlalchemy import select
from datetime import datetime


employeesapp_bp = Blueprint("employeesapp_bp", __name__, url_prefix="/api/employeesapp")


@employeesapp_bp.route("/<int:employee_id>/appointments/upcoming", methods=["GET"])
def get_upcoming_appointments(employee_id):
    """
    GET /api/employeesapp/<employee_id>/appointments/upcoming
    Purpose: Fetch an employee's upcoming appointments.
    """
    if not db.session.get(Employees, employee_id):
        return jsonify({"error": "Employee not found"}), 404

    now = datetime.utcnow()

    stmt = (
        select(
            Appointment,
            Service.name.label("service_name"),
            Salon.name.label("salon_name"),
            Customers.first_name.label("customer_first_name"),
            Customers.last_name.label("customer_last_name"),
        )
        .outerjoin(Service, Appointment.service_id == Service.id)
        .outerjoin(Salon, Appointment.salon_id == Salon.id)
        .outerjoin(Customers, Appointment.customer_id == Customers.id)
        .where(
            Appointment.employee_id == employee_id,
            Appointment.start_at >= now,
            Appointment.status.notin_(["CANCELLED", "COMPLETED", "NO_SHOW"]),
        )
        .order_by(Appointment.start_at.asc())
    )

    results = db.session.execute(stmt).all()

    appointments_list = [
        {
            "appointment_id": appt.id,
            "service_name": service_name,
            "salon_name": salon_name,
            "start_at": appt.start_at.isoformat(),
            "end_at": appt.end_at.isoformat(),
            "customer_name": f"{first_name} {last_name}".strip(),
            "status": appt.status,
            "notes": appt.notes,
        }
        for appt, service_name, salon_name, first_name, last_name in results
    ]

    return jsonify(appointments_list), 200


@employeesapp_bp.route("/<int:employee_id>/appointments/previous", methods=["GET"])
def get_previous_appointments(employee_id):
    """
    GET /api/employeesapp/<employee_id>/appointments/previous
    Purpose: Fetch an employee's previous appointments.
    """
    if not db.session.get(Employees, employee_id):
        return jsonify({"error": "Employee not found"}), 404

    now = datetime.utcnow()

    stmt = (
        select(
            Appointment,
            Service.name.label("service_name"),
            Salon.name.label("salon_name"),
            Customers.first_name.label("customer_first_name"),
            Customers.last_name.label("customer_last_name"),
        )
        .outerjoin(Service, Appointment.service_id == Service.id)
        .outerjoin(Salon, Appointment.salon_id == Salon.id)
        .outerjoin(Customers, Appointment.customer_id == Customers.id)
        .where(
            Appointment.employee_id == employee_id,
            (
                (Appointment.start_at < now)
                | (Appointment.status.in_(["CANCELLED", "COMPLETED", "NO_SHOW"]))
            ),
        )
        .order_by(Appointment.start_at.desc())
    )

    results = db.session.execute(stmt).all()

    appointments_list = [
        {
            "appointment_id": appt.id,
            "service_name": service_name,
            "salon_name": salon_name,
            "start_at": appt.start_at.isoformat(),
            "end_at": appt.end_at.isoformat(),
            "customer_name": f"{first_name} {last_name}".strip(),
            "status": appt.status,
            "notes": appt.notes,
        }
        for appt, service_name, salon_name, first_name, last_name in results
    ]

    return jsonify(appointments_list), 200


@employeesapp_bp.route(
    "/<int:employee_id>/appointments/<int:appointment_id>", methods=["PUT"]
)
def edit_upcoming_appointment(employee_id, appointment_id):
    """
    PUT /api/employeesapp/<employee_id>/appointments/<appointment_id>
    Purpose: Edit the details of an upcoming appointment.
    Input: JSON body with optional fields:
        - start_at (isoformat string)
        - end_at (isoformat string)
        - service_id (int)
        - notes (string)
    """
    appt = db.session.get(Appointment, appointment_id)

    if not appt:
        return jsonify({"error": "Appointment not found"}), 404
    if appt.employee_id != employee_id:
        return jsonify({"error": "Forbidden: You cannot edit this appointment"}), 403
    if appt.start_at < datetime.utcnow():
        return jsonify({"error": "Cannot edit a past appointment"}), 400
    if appt.status in ["CANCELLED", "COMPLETED", "NO_SHOW"]:
        return (
            jsonify(
                {"error": f"Cannot edit an appointment with status: {appt.status}"}
            ),
            400,
        )

    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400

    try:
        if "start_at" in data and data["start_at"]:
            appt.start_at = datetime.fromisoformat(data["start_at"])
        if "end_at" in data and data["end_at"]:
            appt.end_at = datetime.fromisoformat(data["end_at"])
        if "service_id" in data:
            appt.service_id = data["service_id"]
        if "notes" in data:
            appt.notes = data["notes"]

        db.session.commit()
        return jsonify({"message": "Appointment updated", "id": appt.id}), 200

    except ValueError as e:
        db.session.rollback()
        return jsonify({"error": "Invalid date format", "details": str(e)}), 400
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": "Database error", "details": str(e)}), 500


@employeesapp_bp.route(
    "/<int:employee_id>/appointments/<int:appointment_id>", methods=["GET"]
)
def get_single_appointment(employee_id, appointment_id):
    """
    GET /api/employeesapp/<employee_id>/appointments/<appointment_id>
    Purpose: Fetch full details of one appointment for editing/viewing.
    """

    appt = db.session.get(Appointment, appointment_id)
    if not appt:
        return jsonify({"error": "Appointment not found"}), 404

    if appt.employee_id != employee_id:
        return jsonify({"error": "Forbidden: You cannot view this appointment"}), 403

    # Fetch related models
    service = db.session.get(Service, appt.service_id) if appt.service_id else None
    salon = db.session.get(Salon, appt.salon_id) if appt.salon_id else None
    customer = db.session.get(Customers, appt.customer_id) if appt.customer_id else None

    # If you eventually add an AppointmentPhoto model, load them here
    photos = []
    # Example:
    # photos = [photo.url for photo in appt.photos]  # if relationship exists

    response = {
        "appointment_id": appt.id,
        "employee_id": appt.employee_id,
        "customer_id": appt.customer_id,
        "customer_name": (
            f"{customer.first_name} {customer.last_name}".strip() if customer else None
        ),
        "service_id": appt.service_id,
        "service_name": service.name if service else None,
        "salon_id": appt.salon_id,
        "salon_name": salon.name if salon else None,
        "start_at": appt.start_at.isoformat(),
        "end_at": appt.end_at.isoformat(),
        "status": appt.status,
        "notes": appt.notes,
        "photos": photos,  # empty array for now
    }

    return jsonify(response), 200


@employeesapp_bp.route(
    "/<int:employee_id>/appointments/<int:appointment_id>/cancel", methods=["PUT"]
)
def cancel_upcoming_appointment(employee_id, appointment_id):
    """
    PUT /api/employeesapp/<employee_id>/appointments/<appointment_id>/cancel
    Purpose: Cancels an upcoming appointment by setting its status.
    Input: Optional JSON body with:
        - reason (string) -> will be added to notes.
    """
    appt = db.session.get(Appointment, appointment_id)

    if not appt:
        return jsonify({"error": "Appointment not found"}), 404
    if appt.employee_id != employee_id:
        return jsonify({"error": "Forbidden: You cannot cancel this appointment"}), 403
    if appt.start_at < datetime.utcnow():
        return jsonify({"error": "Cannot cancel a past appointment"}), 400
    if appt.status == "CANCELLED":
        return jsonify({"error": "Appointment is already cancelled"}), 400
    if appt.status in ["COMPLETED", "NO_SHOW"]:
        return (
            jsonify(
                {"error": f"Cannot cancel an appointment with status: {appt.status}"}
            ),
            400,
        )

    data = request.get_json()
    reason = data.get("reason") if data else None

    try:
        appt.status = "CANCELLED"
        if reason:
            new_note = f"Cancelled by employee. Reason: {reason}"
            appt.notes = f"{appt.notes}\n{new_note}" if appt.notes else new_note

        db.session.commit()

        return (
            jsonify(
                {
                    "message": "Appointment cancelled",
                    "id": appt.id,
                    "status": appt.status,
                }
            ),
            200,
        )

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": "Database error", "details": str(e)}), 500


@employeesapp_bp.route(
    "/<int:employee_id>/appointments/<int:appointment_id>/message", methods=["POST"]
)
def send_message_to_customer(employee_id, appointment_id):
    """
    POST /api/employeesapp/<employee_id>/appointments/<appointment_id>/message
    Purpose: Send a message to the customer associated with this appointment.
    Input: JSON body with:
        - body (required, string): The message text.
    """
    appt = db.session.get(Appointment, appointment_id)

    if not appt:
        return jsonify({"error": "Appointment not found"}), 404
    if appt.employee_id != employee_id:
        return jsonify({"error": "Forbidden: Not your appointment"}), 403
    if not appt.customer_id:
        return jsonify({"error": "Appointment has no customer associated"}), 404

    data = request.get_json()
    body = data.get("body")
    if not body:
        return jsonify({"error": "Message 'body' is required"}), 400

    try:
        new_msg = Message(
            customer_id=appt.customer_id,
            employee_id=employee_id,
            sender_role="EMPLOYEE",
            body=body,
        )
        db.session.add(new_msg)
        db.session.commit()

        return (
            jsonify(
                {
                    "message": "Message sent",
                    "message_id": new_msg.id,
                    "customer_id": new_msg.customer_id,
                    "employee_id": new_msg.employee_id,
                    "body": new_msg.body,
                    "created_at": new_msg.created_at.isoformat(),
                }
            ),
            201,
        )

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": "Database error", "details": str(e)}), 500


@employeesapp_bp.route(
    "/<int:employee_id>/appointments/<int:appointment_id>/images", methods=["GET"]
)
def get_appointment_images(employee_id, appointment_id):
    appt = db.session.get(Appointment, appointment_id)
    if not appt:
        return jsonify({"error": "Appointment not found"}), 404
    if appt.employee_id != employee_id:
        return jsonify({"error": "Unauthorized"}), 403

    images = db.session.scalars(
        select(AppointmentImage).where(
            AppointmentImage.appointment_id == appointment_id
        )
    ).all()

    return (
        jsonify(
            {
                "appointment_id": appointment_id,
                "count": len(images),
                "images": [
                    {"id": img.id, "url": img.url, "created_at": img.created_at}
                    for img in images
                ],
            }
        ),
        200,
    )
