from flask import Blueprint, request, jsonify
from ...extensions import db
from ...models import Employees, AuthUser

employee_details_bp = Blueprint("employee_details", __name__, url_prefix="/api/employee/details")


@employee_details_bp.route("/<int:employee_id>", methods=["GET"])
def get_employee_details(employee_id):
    """
    Get employee details by employee ID
    ---
    tags:
      - Employee Details
    parameters:
      - in: path
        name: employee_id
        type: integer
        required: true
        description: Employee ID
    responses:
      200:
        description: Employee details retrieved successfully
        schema:
          type: object
          properties:
            status:
              type: string
              example: success
            data:
              type: object
              properties:
                id:
                  type: integer
                first_name:
                  type: string
                last_name:
                  type: string
                phone_number:
                  type: string
                address:
                  type: string
                employment_status:
                  type: string
                employee_type:
                  type: string
                email:
                  type: string
                salon_id:
                  type: integer
      404:
        description: Employee not found
        schema:
          type: object
          properties:
            status:
              type: string
              example: error
            message:
              type: string
    """
    try:
        employee = db.session.get(Employees, employee_id)
        if not employee:
            return jsonify({"status": "error", "message": "Employee not found"}), 404

        user = db.session.get(AuthUser, employee.user_id)
        email = user.email if user else None

        return (
            jsonify(
                {
                    "status": "success",
                    "data": {
                        "id": employee.id,
                        "first_name": employee.first_name,
                        "last_name": employee.last_name,
                        "phone_number": employee.phone_number,
                        "address": employee.address,
                        "employment_status": employee.employment_status,
                        "employee_type": employee.employee_type,
                        "email": email,
                        "salon_id": employee.salon_id,
                    },
                }
            ),
            200,
        )
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@employee_details_bp.route("/<int:employee_id>", methods=["PUT"])
def edit_employee_details(employee_id):
    """
    Edit employee details (first_name, last_name, phone_number, address, employment_status, employee_type, salon_id)
    ---
    tags:
      - Employee Details
    parameters:
      - in: path
        name: employee_id
        type: integer
        required: true
        description: Employee ID
      - in: body
        name: body
        required: true
        schema:
          type: object
          properties:
            first_name:
              type: string
              description: Employee first name (optional)
            last_name:
              type: string
              description: Employee last name (optional)
            phone_number:
              type: string
              description: Employee phone number (optional)
            address:
              type: string
              description: Employee address (optional)
            employment_status:
              type: string
              description: Employee employment status (optional)
            employee_type:
              type: string
              description: Employee type (optional)
            salon_id:
              type: integer
              description: Salon ID (optional)
    responses:
      200:
        description: Employee details updated successfully
        schema:
          type: object
          properties:
            status:
              type: string
              example: success
            message:
              type: string
            data:
              type: object
              properties:
                id:
                  type: integer
                first_name:
                  type: string
                last_name:
                  type: string
                phone_number:
                  type: string
                address:
                  type: string
                employment_status:
                  type: string
                employee_type:
                  type: string
                salon_id:
                  type: integer
      400:
        description: Invalid request body
        schema:
          type: object
          properties:
            status:
              type: string
              example: error
            message:
              type: string
      404:
        description: Employee not found
        schema:
          type: object
          properties:
            status:
              type: string
              example: error
            message:
              type: string
      500:
        description: Server error
        schema:
          type: object
          properties:
            status:
              type: string
              example: error
            message:
              type: string
    """
    try:
        data = request.get_json(silent=True)
        if not data:
            return (
                jsonify(
                    {
                        "status": "error",
                        "message": "No valid JSON body found. Ensure Content-Type is application/json.",
                    }
                ),
                400,
            )

        employee = db.session.get(Employees, employee_id)
        if not employee:
            return jsonify({"status": "error", "message": "Employee not found"}), 404

        # Update optional fields if provided
        if "first_name" in data:
            employee.first_name = data["first_name"]
        if "last_name" in data:
            employee.last_name = data["last_name"]
        if "phone_number" in data:
            employee.phone_number = data["phone_number"]
        if "address" in data:
            employee.address = data["address"]
        if "employment_status" in data:
            employee.employment_status = data["employment_status"]
        if "employee_type" in data:
            employee.employee_type = data["employee_type"]
        if "salon_id" in data:
            employee.salon_id = data["salon_id"]

        db.session.commit()

        return (
            jsonify(
                {
                    "status": "success",
                    "message": "Employee details updated successfully",
                    "data": {
                        "id": employee.id,
                        "first_name": employee.first_name,
                        "last_name": employee.last_name,
                        "phone_number": employee.phone_number,
                        "address": employee.address,
                        "employment_status": employee.employment_status,
                        "employee_type": employee.employee_type,
                        "salon_id": employee.salon_id,
                    },
                }
            ),
            200,
        )
    except Exception as e:
        db.session.rollback()
        return jsonify({"status": "error", "message": str(e)}), 500
