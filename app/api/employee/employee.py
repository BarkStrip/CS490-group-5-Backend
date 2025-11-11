from flask import Blueprint, jsonify, request
from app.extensions import db
# Removed the non-existent Enum import
from app.models import Employees, EmpAvail 
from sqlalchemy import select, delete
from datetime import time, date

employees_bp = Blueprint("employees", __name__, url_prefix="/api/employees")


@employees_bp.route("/<int:employee_id>/schedule", methods=["GET"])
def get_employee_schedule(employee_id):
    """
    GET /api/employees/<employee_id>/schedule
    Purpose: Fetch an employee's schedule, their active status, and their work type.
    """
    
    # Get the employee
    employee = db.session.get(Employees, employee_id)
    if not employee:
        return jsonify({"error": "Employee not found"}), 404
        
    stmt = (
        select(EmpAvail)
        .where(EmpAvail.employee_id == employee_id)
        .order_by(EmpAvail.weekday, EmpAvail.effective_from.desc())
    )
    schedule_rules = db.session.scalars(stmt).all()
    
    schedule_list = [
        {
            "id": rule.id,
            "weekday": rule.weekday,
            "start_time": rule.start_time.isoformat() if rule.start_time else None,
            "end_time": rule.end_time.isoformat() if rule.end_time else None,
            "effective_from": rule.effective_from.isoformat() if rule.effective_from else None,
            "effective_to": rule.effective_to.isoformat() if rule.effective_to else None,
        }
        for rule in schedule_rules
    ]
    
    result = {
        "employee_id": employee.id,
        "employment_status": employee.employment_status if employee.employment_status else None, # e.g., "ACTIVE"
        "employee_type": employee.employee_type if employee.employee_type else None, # e.g., "PART_TIME"
        "schedule": schedule_list
    }
    
    return jsonify(result), 200


@employees_bp.route("/<int:employee_id>/schedule", methods=["PUT"])
def update_employee_schedule(employee_id):
    """
    PUT /api/employees/<employee_id>/schedule
    Purpose: Update/replace an employee's entire weekly working schedule.

    """
    
    # Get the employee
    employee = db.session.get(Employees, employee_id)
    if not employee:
        return jsonify({"error": "Employee not found"}), 404

    data = request.get_json()
    if not data or "schedule" not in data or not isinstance(data["schedule"], list):
        return jsonify({"error": "Invalid input. 'schedule' list is required."}), 400
        
    new_schedule_data = data["schedule"]
    today = date.today()
    new_schedule_rules = []

    try:
        stmt_delete = delete(EmpAvail).where(EmpAvail.employee_id == employee_id)
        db.session.execute(stmt_delete)

        for rule_data in new_schedule_data:
            weekday = rule_data.get("weekday")
            start_str = rule_data.get("start_time")
            end_str = rule_data.get("end_time")

            if weekday not in range(0, 7):
                raise ValueError(f"Invalid weekday: {weekday}")

            if start_str and end_str:
                new_rule = EmpAvail(
                    employee_id=employee_id,
                    weekday=weekday,
                    start_time=time.fromisoformat(start_str),
                    end_time=time.fromisoformat(end_str),
                    effective_from=today
                )
                db.session.add(new_rule)
                new_schedule_rules.append(new_rule)
        
        db.session.commit()
        
        created_list = [
            {
                "id": rule.id,
                "weekday": rule.weekday,
                "start_time": rule.start_time.isoformat(),
                "end_time": rule.end_time.isoformat(),
                "effective_from": rule.effective_from.isoformat(),
            }
            for rule in new_schedule_rules
        ]

        return jsonify(created_list), 200

    except ValueError as e:
        db.session.rollback()
        return jsonify({"error": f"Invalid data format: {str(e)}"}), 400
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": "Database error", "details": str(e)}), 500


@employees_bp.route("/<int:employee_id>/status", methods=["PUT"])
def update_employee_status(employee_id):
    """
    PUT /api/employees/<employee_id>/status
    Purpose: CORRECTED - Edits an employee's active status (e.g., "ACTIVE", "INACTIVE").
    Input: JSON body with:
        - employment_status (required): "ACTIVE", "INACTIVE", "ON_LEAVE", etc.
    """
    
    employee = db.session.get(Employees, employee_id)
    if not employee:
        return jsonify({"error": "Employee not found"}), 404

    data = request.get_json()
    new_status_str = data.get("employment_status") 

    if not new_status_str:
        return jsonify({"error": "employment_status is required"}), 400

    if len(new_status_str) > 15:
        return jsonify({
            "error": "Invalid employment_status",
            "details": f"Must be 15 characters or less (e.g., 'ACTIVE')."
        }), 400
        
    try:
        employee.employment_status = new_status_str
        db.session.commit()

        return jsonify({
            "id": employee.id,
            "first_name": employee.first_name,
            "employment_status": employee.employment_status
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": "Database error", "details": str(e)}), 500


@employees_bp.route("/<int:employee_id>/type", methods=["PUT"])
def update_employee_type(employee_id):
    """
    PUT /api/employees/<int:employee_id>/type
    Purpose: NEW - Edits an employee's work arrangement (e.g., "PART_TIME", "FULL_TIME").
    Input: JSON body with:
        - employee_type (required): "PART_TIME", "FULL_TIME", "CONTRACTOR"
    """
    
    employee = db.session.get(Employees, employee_id)
    if not employee:
        return jsonify({"error": "Employee not found"}), 404

    data = request.get_json()
    new_type_str = data.get("employee_type")

    if not new_type_str:
        return jsonify({"error": "employee_type is required"}), 400

    if len(new_type_str) > 50:
        return jsonify({
            "error": "Invalid employee_type",
            "details": f"Must be 50 characters or less (e.g., 'PART_TIME')."
        }), 400
        
    try:
        employee.employee_type = new_type_str
        db.session.commit()

        return jsonify({
            "id": employee.id,
            "first_name": employee.first_name,
            "employee_type": employee.employee_type
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": "Database error", "details": str(e)}), 500