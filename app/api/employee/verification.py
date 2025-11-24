from flask import Blueprint, jsonify, request
from app.extensions import db
from app.models import Employees, Salon, AuthUser
from datetime import datetime
import traceback

# Create the Blueprint
employee_verification_bp = Blueprint(
    "employee_verification", __name__, url_prefix="/api/employee/verification"
)


@employee_verification_bp.route("/<int:salon_id>", methods=["GET"])
def get_employees_verification(salon_id):
    """
    GET /api/employee/verification/<int:salon_id> - Get employees for verification at a salon

    ---
    summary: Retrieve employees awaiting verification for a specific salon
    description: Fetches all employees with specified verification status for the specified salon
    parameters:
      - name: salon_id
        in: path
        type: integer
        required: true
        description: The salon ID to fetch employees for verification
      - name: status
        in: query
        type: string
        enum: [PENDING, APPROVED, REJECTED]
        required: false
        description: Filter by verification status (default PENDING)
    responses:
      200:
        description: Returns array of employees with verification details
      404:
        description: Salon not found
      500:
        description: Database error
    """
    try:
        # Get query parameters
        status_filter = request.args.get("status", "PENDING")

        # Check if salon exists
        salon = db.session.query(Salon).filter(Salon.id == salon_id).first()
        if not salon:
            return jsonify({"status": "error", "message": "Salon not found"}), 404

        # Get employees for this salon with status filter
        employees = (
            db.session.query(Employees)
            .filter(
                Employees.salon_id == salon_id,
                Employees.employment_status == status_filter,
            )
            .all()
        )

        # Format response
        employee_list = []
        for emp in employees:
            employee_list.append(
                {
                    "id": emp.id,
                    "user_id": emp.user_id,
                    "salon_id": emp.salon_id,
                    "first_name": emp.first_name,
                    "last_name": emp.last_name,
                    "phone_number": emp.phone_number,
                    "address": emp.address,
                    "employment_status": emp.employment_status,
                    "employee_type": emp.employee_type,
                    "email": emp.user.email if emp.user else None,
                    "created_at": (
                        emp.created_at.isoformat() if emp.created_at else None
                    ),
                    "updated_at": (
                        emp.updated_at.isoformat() if emp.updated_at else None
                    ),
                }
            )

        return (
            jsonify(
                {
                    "status": "success",
                    "salon_id": salon_id,
                    "salon_name": salon.name,
                    "employees": employee_list,
                }
            ),
            200,
        )

    except Exception as e:
        traceback.print_exc()
        return (
            jsonify(
                {
                    "status": "error",
                    "message": "Failed to fetch pending employees",
                    "details": str(e),
                }
            ),
            500,
        )


@employee_verification_bp.route("/<int:employee_id>", methods=["PUT"])
def update_employee_status(employee_id):
    """
    PUT /api/employee/verification/<int:employee_id> - Update employee verification status

    ---
    summary: Approve or reject employee verification
    description: Changes employee verification status (PENDING/APPROVED/REJECTED)
    parameters:
      - name: employee_id
        in: path
        type: integer
        required: true
        description: The employee ID to update
    requestBody:
      required: true
      schema:
        type: object
        properties:
          employment_status:
            type: string
            enum: [PENDING, APPROVED, REJECTED]
            description: New verification status (required)
        required:
          - employment_status
    responses:
      200:
        description: Employee verification status updated successfully
      400:
        description: Invalid status value
      404:
        description: Employee not found
      500:
        description: Database error
    """
    try:
        data = request.get_json()
        new_status = data.get("employment_status", "").upper()

        # Validate status
        if new_status not in ["PENDING", "APPROVED", "REJECTED"]:
            return (
                jsonify(
                    {
                        "status": "error",
                        "message": "Invalid employment_status. Must be PENDING, APPROVED, or REJECTED",
                    }
                ),
                400,
            )

        # Find employee
        employee = (
            db.session.query(Employees).filter(Employees.id == employee_id).first()
        )

        if not employee:
            return jsonify({"status": "error", "message": "Employee not found"}), 404

        # Update employment status
        employee.employment_status = new_status
        employee.updated_at = datetime.utcnow()
        db.session.commit()

        # Fetch user email
        user = (
            db.session.query(AuthUser).filter(AuthUser.id == employee.user_id).first()
        )

        return (
            jsonify(
                {
                    "status": "success",
                    "message": f"Employee status updated to {new_status}",
                    "employee": {
                        "id": employee.id,
                        "user_id": employee.user_id,
                        "salon_id": employee.salon_id,
                        "first_name": employee.first_name,
                        "last_name": employee.last_name,
                        "phone_number": employee.phone_number,
                        "address": employee.address,
                        "employment_status": employee.employment_status,
                        "employee_type": employee.employee_type,
                        "email": user.email if user else None,
                        "updated_at": (
                            employee.updated_at.isoformat()
                            if employee.updated_at
                            else None
                        ),
                    },
                }
            ),
            200,
        )

    except Exception as e:
        db.session.rollback()
        traceback.print_exc()
        return (
            jsonify(
                {
                    "status": "error",
                    "message": "Failed to update employee status",
                    "details": str(e),
                }
            ),
            500,
        )
