# Book, edit, cancel appointments and set availability
from flask import Blueprint, jsonify, request
from app.extensions import db
from ...models import (
    Salon,
    Employees,
    EmpAvail,
    Appointment,
    Customers,
    TimeBlock,
    Service,
)
from datetime import timedelta
import datetime

from sqlalchemy import and_, or_, select

appointments_bp = Blueprint("appointments", __name__, url_prefix="/api/appointments")


@appointments_bp.route("/<int:salon_id>/hours", methods=["GET"])
def get_salon_hours(salon_id):
    """
    GET /api/appointments/<salon_id>/hours
    Purpose: Fetches the operating hours for a specific salon.
    Input: salon_id (integer) from the URL path.

    Behavior:
    - If salon_id is valid:
        → Return a list of all SalonHours objects for that salon.
    - If no hours are set:
        → Return an empty list [].
    - If salon_id does not exist:
        → Return a 404 error.
    """

    salon = db.session.get(Salon, salon_id)

    if not salon:
        return jsonify({"error": "Salon not found"}), 404

    hours_list = salon.salon_hours

    results = [
        {
            "id": hour.id,
            "salon_id": hour.salon_id,
            "weekday": hour.weekday,
            "is_open": hour.is_open,
            "open_time": hour.open_time.isoformat() if hour.open_time else None,
            "close_time": hour.close_time.isoformat() if hour.close_time else None,
        }
        for hour in hours_list
    ]

    return jsonify(results)


@appointments_bp.route("/<int:salon_id>/employees", methods=["GET"])
def get_salon_employees(salon_id):
    """
    GET /api/salons/<salon_id>/employees
    Purpose: Fetches all employees associated with a specific salon.
    Input: salon_id (integer) from the URL path.

    Behavior:
    - If salon_id is valid:
        → Return a list of all Employee objects for that salon.
    - If no employees are found:
        → Return an empty list [].
    - If salon_id does not exist:
        → Return a 404 error.
    """

    # First, get the salon to ensure it exists
    salon = db.session.get(Salon, salon_id)

    if not salon:
        return jsonify({"error": "Salon not found"}), 404

    # Access the 'employees' relationship from the Salon model
    # SQLAlchemy will efficiently fetch the related employees
    employees_list = salon.employees

    # Serialize the list of Employees objects
    # We only include key info needed for a list (e.g., for booking)
    results = [
        {
            "id": emp.id,  # This is the employee_id
            "first_name": emp.first_name,
            "last_name": emp.last_name,
            "phone_number": emp.phone_number,
            "employment_status": emp.employment_status,
            "user_id": emp.user_id,  # The associated auth user ID
        }
        for emp in employees_list
    ]

    return jsonify(results)


@appointments_bp.route("/<int:employee_id>/availability", methods=["GET"])
def get_employee_availability(employee_id):
    """
    GET /api/employees/<employee_id>/availability
    Purpose: Fetches the availability (working hours) for a specific employee.
    Input: employee_id (integer) from the URL path.

    Behavior:
    - If employee_id is valid:
        → Return a list of all EmpAvail objects for that employee.
    - If no availability is set:
        → Return an empty list [].
    - If employee_id does not exist:
        → Return a 404 error.
    """

    # Use db.session.get() for an efficient lookup by primary key
    employee = db.session.get(Employees, employee_id)

    # Handle the case where the employee doesn't exist
    if not employee:
        return jsonify({"error": "Employee not found"}), 404

    # Access the 'emp_avail' relationship defined in your Employees model
    availability_list = employee.emp_avail

    # Serialize the list of EmpAvail objects into a JSON-friendly format
    results = [
        {
            "id": avail.id,
            "employee_id": avail.employee_id,
            "weekday": avail.weekday,
            # Use .isoformat() for Time and Date objects
            "start_time": avail.start_time.isoformat() if avail.start_time else None,
            "end_time": avail.end_time.isoformat() if avail.end_time else None,
            "effective_from": (
                avail.effective_from.isoformat() if avail.effective_from else None
            ),
            "effective_to": (
                avail.effective_to.isoformat() if avail.effective_to else None
            ),
        }
        for avail in availability_list
    ]

    # Return the JSON-formatted list
    return jsonify(results)


@appointments_bp.route("/<int:employee_id>/available-times", methods=["GET"])
def get_employee_available_times(employee_id):
    """
    GET /api/employees/<employee_id>/available-times?date=YYYY-MM-DD&duration=MINUTES
    Purpose: Calculate actual available appointment slots for a given employee,
             date, and service duration.
    """

    date_str = request.args.get("date")
    if not date_str:
        return (
            jsonify({"error": "Missing required query parameter: 'date' (YYYY-MM-DD)"}),
            400,
        )

    duration_str = request.args.get("duration")
    if not duration_str:
        return (
            jsonify(
                {"error": "Missing required query parameter: 'duration' (in minutes)"}
            ),
            400,
        )

    try:
        selected_date = datetime.date.fromisoformat(date_str)
        duration_minutes = int(duration_str)
        service_duration = datetime.timedelta(minutes=duration_minutes)
    except (ValueError, TypeError):
        return jsonify({"error": "Invalid 'date' or 'duration' format."}), 400

    employee = db.session.get(Employees, employee_id)
    if not employee:
        return jsonify({"error": "Employee not found"}), 404

    weekday_iso = selected_date.isoweekday()
    weekday_model = weekday_iso % 7

    base_avail = (
        db.session.query(EmpAvail)
        .filter(
            and_(
                EmpAvail.employee_id == employee_id,
                EmpAvail.weekday == weekday_model,
                EmpAvail.effective_from <= selected_date,
                or_(
                    EmpAvail.effective_to is None,
                    EmpAvail.effective_to >= selected_date,
                ),
            )
        )
        .first()
    )

    if not base_avail or not base_avail.start_time or not base_avail.end_time:
        return jsonify([])

    start_of_day = datetime.datetime.combine(selected_date, datetime.time.min)
    end_of_day = datetime.datetime.combine(selected_date, datetime.time.max)

    busy_appointments = (
        db.session.query(Appointment.start_at, Appointment.end_at)
        .filter(
            and_(
                Appointment.employee_id == employee_id,
                Appointment.start_at >= start_of_day,
                Appointment.end_at <= end_of_day,
                Appointment.status.in_(["BOOKED", "CONFIRMED", "PENDING"]),
            )
        )
        .all()
    )

    busy_time_blocks = (
        db.session.query(TimeBlock.start_at, TimeBlock.end_at)
        .filter(
            and_(
                TimeBlock.employee_id == employee_id,
                TimeBlock.start_at >= start_of_day,
                TimeBlock.end_at <= end_of_day,
            )
        )
        .all()
    )

    busy_intervals = sorted(
        busy_appointments + busy_time_blocks, key=lambda x: x.start_at
    )

    available_slots = []
    slot_increment = datetime.timedelta(minutes=15)

    current_time = datetime.datetime.combine(selected_date, base_avail.start_time)
    end_of_shift = datetime.datetime.combine(selected_date, base_avail.end_time)

    while (current_time + service_duration) <= end_of_shift:

        slot_end_time = current_time + service_duration
        is_available = True

        for busy_start, busy_end in busy_intervals:

            if current_time < busy_end and slot_end_time > busy_start:
                is_available = False
                break

        if is_available:
            available_slots.append(current_time.time().isoformat())

        current_time += slot_increment

    return jsonify(available_slots)


@appointments_bp.route("/<int:customer_id>/upcoming", methods=["GET"])
def get_upcoming_appointments(customer_id):
    """
    GET /api/appointments/<customer_id>/upcoming
    Purpose: Retrieve all future appointments for a specific customer.
    Input: customer_id (integer) from the URL path.

    Behavior:
    - If customer_id is valid:
        → Return a list of all Appointment objects where start_at > current datetime,
          ordered by start_at (earliest first).
    - If no upcoming appointments are found:
        → Return an empty list [].
    - If customer_id does not exist:
        → Return a 404 error.
    """

    # Check if customer exists
    customer = db.session.get(Customers, customer_id)

    if not customer:
        return jsonify({"error": "Customer not found"}), 404

    # Get current datetime
    now = datetime.datetime.now()

    # Query for upcoming appointments (start_at > now), ordered by start_at
    upcoming_appointments = (
        db.session.query(Appointment)
        .filter(
            and_(Appointment.customer_id == customer_id, Appointment.start_at > now)
        )
        .order_by(Appointment.start_at)
        .all()
    )

    # Serialize the appointments with all fields (flattened)
    results = [
        {
            "id": apt.id,
            "salon_id": apt.salon_id,
            "salon_name": apt.salon.name if apt.salon else None,
            "salon_phone": apt.salon.phone if apt.salon else None,
            "salon_address": apt.salon.address if apt.salon else None,
            "customer_id": apt.customer_id,
            "employee_id": apt.employee_id,
            "employee_first_name": apt.employee.first_name if apt.employee else None,
            "employee_last_name": apt.employee.last_name if apt.employee else None,
            "employee_phone": apt.employee.phone_number if apt.employee else None,
            "service_id": apt.service_id,
            "service_name": apt.service.name if apt.service else None,
            "service_duration": apt.service.duration if apt.service else None,
            "service_price": (
                float(apt.service.price) if apt.service and apt.service.price else None
            ),
            "start_at": apt.start_at.isoformat() if apt.start_at else None,
            "end_at": apt.end_at.isoformat() if apt.end_at else None,
            "status": apt.status,
            "price_at_book": float(apt.price_at_book) if apt.price_at_book else None,
            "notes": apt.notes,
        }
        for apt in upcoming_appointments
    ]

    return jsonify(results)


@appointments_bp.route("/<int:customer_id>/previous", methods=["GET"])
def get_previous_appointments(customer_id):
    """
    GET /api/appointments/<customer_id>/previous
    Purpose: Retrieve all completed past appointments for a specific customer.
    Input: customer_id (integer) from the URL path.

    Behavior:
    - If customer_id is valid:
        → Return a list of all Appointment objects where start_at < current datetime
          AND status = 'COMPLETED', ordered by start_at (most recent first).
    - If no completed previous appointments are found:
        → Return an empty list [].
    - If customer_id does not exist:
        → Return a 404 error.
    """

    # Check if customer exists
    customer = db.session.get(Customers, customer_id)

    if not customer:
        return jsonify({"error": "Customer not found"}), 404

    # Get current datetime
    now = datetime.datetime.now()

    # Query for completed previous appointments (start_at < now AND status = 'COMPLETED'), ordered by start_at descending (most recent first)
    previous_appointments = (
        db.session.query(Appointment)
        .filter(
            and_(
                Appointment.customer_id == customer_id,
                Appointment.start_at < now,
                Appointment.status == "COMPLETED",
            )
        )
        .order_by(Appointment.start_at.desc())
        .all()
    )

    # Serialize the appointments with all fields (flattened)
    results = [
        {
            "id": apt.id,
            "salon_id": apt.salon_id,
            "salon_name": apt.salon.name if apt.salon else None,
            "salon_phone": apt.salon.phone if apt.salon else None,
            "salon_address": apt.salon.address if apt.salon else None,
            "customer_id": apt.customer_id,
            "employee_id": apt.employee_id,
            "employee_first_name": apt.employee.first_name if apt.employee else None,
            "employee_last_name": apt.employee.last_name if apt.employee else None,
            "employee_phone": apt.employee.phone_number if apt.employee else None,
            "service_id": apt.service_id,
            "service_name": apt.service.name if apt.service else None,
            "service_duration": apt.service.duration if apt.service else None,
            "service_price": (
                float(apt.service.price) if apt.service and apt.service.price else None
            ),
            "start_at": apt.start_at.isoformat() if apt.start_at else None,
            "end_at": apt.end_at.isoformat() if apt.end_at else None,
            "status": apt.status,
            "price_at_book": float(apt.price_at_book) if apt.price_at_book else None,
            "notes": apt.notes,
        }
        for apt in previous_appointments
    ]

    return jsonify(results)


@appointments_bp.route(
    "/<int:customer_id>/appointments/<int:appointment_id>", methods=["PUT"]
)
def edit_appointment(customer_id, appointment_id):
    """
    PUT /api/appointments/<customer_id>/appointments/<appointment_id>
    Purpose: Update an appointment for a specific customer.
    Input:
        - customer_id (integer) from the URL path
        - appointment_id (integer) from the URL path
        - JSON body with optional fields to update:
          * employee_id
          * service_id
          * start_at (ISO format: YYYY-MM-DDTHH:MM:SS)
          * end_at (ISO format: YYYY-MM-DDTHH:MM:SS)
          * status (e.g., BOOKED, CONFIRMED, PENDING, COMPLETED, CANCELLED)
          * price_at_book
          * notes

    Behavior:
    - If customer_id or appointment_id does not exist:
        → Return a 404 error.
    - If the appointment does not belong to the customer:
        → Return a 403 error (Forbidden).
    - If update is successful:
        → Return the updated appointment object with 200 status.
    - If validation fails:
        → Return a 400 error with details.
    """

    # Check if customer exists
    customer = db.session.get(Customers, customer_id)
    if not customer:
        return jsonify({"error": "Customer not found"}), 404

    # Get the appointment
    appointment = db.session.get(Appointment, appointment_id)
    if not appointment:
        return jsonify({"error": "Appointment not found"}), 404

    # Verify the appointment belongs to the customer
    if appointment.customer_id != customer_id:
        return jsonify({"error": "Appointment does not belong to this customer"}), 403

    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "Request body is required"}), 400

        # Update optional fields
        if "employee_id" in data:
            appointment.employee_id = data.get("employee_id")

        if "service_id" in data:
            appointment.service_id = data.get("service_id")

        if "start_at" in data:
            start_at_str = data.get("start_at")
            try:
                appointment.start_at = datetime.datetime.fromisoformat(start_at_str)
            except (ValueError, TypeError):
                return (
                    jsonify(
                        {
                            "error": "start_at must be in ISO format (YYYY-MM-DDTHH:MM:SS)"
                        }
                    ),
                    400,
                )

        if "end_at" in data:
            end_at_str = data.get("end_at")
            try:
                appointment.end_at = datetime.datetime.fromisoformat(end_at_str)
            except (ValueError, TypeError):
                return (
                    jsonify(
                        {"error": "end_at must be in ISO format (YYYY-MM-DDTHH:MM:SS)"}
                    ),
                    400,
                )

        if "status" in data:
            appointment.status = data.get("status")

        if "price_at_book" in data:
            price = data.get("price_at_book")
            if price is not None:
                try:
                    appointment.price_at_book = float(price)
                except (ValueError, TypeError):
                    return (
                        jsonify({"error": "price_at_book must be a valid number"}),
                        400,
                    )

        if "notes" in data:
            appointment.notes = data.get("notes")

        # Commit changes
        db.session.commit()

        # Return the updated appointment
        updated = {
            "id": appointment.id,
            "salon_id": appointment.salon_id,
            "salon_name": appointment.salon.name if appointment.salon else None,
            "salon_phone": appointment.salon.phone if appointment.salon else None,
            "salon_address": appointment.salon.address if appointment.salon else None,
            "customer_id": appointment.customer_id,
            "employee_id": appointment.employee_id,
            "employee_first_name": (
                appointment.employee.first_name if appointment.employee else None
            ),
            "employee_last_name": (
                appointment.employee.last_name if appointment.employee else None
            ),
            "employee_phone": (
                appointment.employee.phone_number if appointment.employee else None
            ),
            "service_id": appointment.service_id,
            "service_name": appointment.service.name if appointment.service else None,
            "service_duration": (
                appointment.service.duration if appointment.service else None
            ),
            "service_price": (
                float(appointment.service.price)
                if appointment.service and appointment.service.price
                else None
            ),
            "start_at": (
                appointment.start_at.isoformat() if appointment.start_at else None
            ),
            "end_at": appointment.end_at.isoformat() if appointment.end_at else None,
            "status": appointment.status,
            "price_at_book": (
                float(appointment.price_at_book) if appointment.price_at_book else None
            ),
            "notes": appointment.notes,
        }

        return jsonify(updated), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": "Database error", "details": str(e)}), 500


@appointments_bp.route("/add", methods=["POST"])
def add_appointment():
    """
    Add a new appointment booking
    ---
    summary: Create a new appointment record in the database
    description: receives booking details from the frontend (bookAppt)
        and stores them in the appointments table. It validates all required fields,
        calculates the appointment end time based on the service duration,
        and saves the appointment in the database.
    tags:
      - Appointments
    parameters:
      - in: body
        name: body
        required: true
        description: JSON payload containing appointment details
    responses:
      201:
        description: Appointment successfully created
      400:
        description: Missing or invalid parameters
      404:
        description: Service not found in database
      500:
        description: Internal server error
    """
    try:
        data = request.get_json()

        required_fields = ["customer_id", "salon_id", "service_id", "start_at"]
        missing = [f for f in required_fields if f not in data]
        if missing:
            return (
                jsonify({"error": f'Missing required fields: {", ".join(missing)}'}),
                400,
            )

        customer_id = data["customer_id"]
        salon_id = data["salon_id"]
        service_id = data["service_id"]
        employee_id = data.get("employee_id")  # can be null for "Any employee"
        start_at_str = data["start_at"]
        notes = data.get("notes")
        status = data.get("status", "Booked")

        try:
            start_at = datetime.datetime.fromisoformat(start_at_str)
            # start_at = datetime.strptime(start_at_str, "%Y-%m-%dT%H:%M:%S")
        except ValueError:
            return (
                jsonify(
                    {
                        "error": "Invalid datetime format for start_at. Use ISO 8601 (e.g. 2025-11-20T11:30:00)"
                    }
                ),
                400,
            )

        service_stmt = select(Service).filter_by(id=service_id)
        service = db.session.scalar(service_stmt)
        if not service:
            return jsonify({"error": "Service not found"}), 404

        duration = getattr(service, "duration", None)
        price = getattr(service, "price", None)
        if duration is None:
            return jsonify({"error": "Service duration missing in DB"}), 400

        end_at = start_at + timedelta(minutes=duration)

        appointment = Appointment(
            salon_id=salon_id,
            customer_id=customer_id,
            employee_id=employee_id,
            service_id=service_id,
            start_at=start_at,
            end_at=end_at,
            status=status,
            price_at_book=price,
            notes=notes,
        )

        db.session.add(appointment)
        db.session.commit()

        return (
            jsonify(
                {
                    "message": "Appointment created successfully",
                    "appointment_id": appointment.id,
                    "start_at": str(appointment.start_at),
                    "end_at": str(appointment.end_at),
                    "status": appointment.status,
                }
            ),
            201,
        )

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500
