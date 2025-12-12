from flask import Blueprint, request, jsonify
from ...extensions import db
from ...models import Admins, AuthUser

admin_details_bp = Blueprint("admin_details", __name__, url_prefix="/api/admin/details")


@admin_details_bp.route("/<int:admin_id>", methods=["GET"])
def get_admin_details(admin_id):
    """
    Get admin details by admin ID
    ---
    tags:
      - Admin Details
    parameters:
      - in: path
        name: admin_id
        type: integer
        required: true
        description: Admin ID
    responses:
      200:
        description: Admin details retrieved successfully
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
                status:
                  type: string
                email:
                  type: string
      404:
        description: Admin not found
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
        admin = db.session.get(Admins, admin_id)
        if not admin:
            return jsonify({"status": "error", "message": "Admin not found"}), 404

        user = db.session.get(AuthUser, admin.user_id)
        email = user.email if user else None

        return (
            jsonify(
                {
                    "status": "success",
                    "data": {
                        "id": admin.id,
                        "first_name": admin.first_name,
                        "last_name": admin.last_name,
                        "phone_number": admin.phone_number,
                        "address": admin.address,
                        "status": admin.status,
                        "email": email,
                    },
                }
            ),
            200,
        )
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@admin_details_bp.route("/<int:admin_id>", methods=["PUT"])
def edit_admin_details(admin_id):
    """
    Edit admin details (first_name, last_name, phone_number, address, status)
    ---
    tags:
      - Admin Details
    parameters:
      - in: path
        name: admin_id
        type: integer
        required: true
        description: Admin ID
      - in: body
        name: body
        required: true
        schema:
          type: object
          properties:
            first_name:
              type: string
              description: Admin first name (optional)
            last_name:
              type: string
              description: Admin last name (optional)
            phone_number:
              type: string
              description: Admin phone number (optional)
            address:
              type: string
              description: Admin address (optional)
            status:
              type: string
              description: Admin status (optional)
    responses:
      200:
        description: Admin details updated successfully
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
                status:
                  type: string
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
        description: Admin not found
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

        admin = db.session.get(Admins, admin_id)
        if not admin:
            return jsonify({"status": "error", "message": "Admin not found"}), 404

        # Update optional fields if provided
        if "first_name" in data:
            admin.first_name = data["first_name"]
        if "last_name" in data:
            admin.last_name = data["last_name"]
        if "phone_number" in data:
            admin.phone_number = data["phone_number"]
        if "address" in data:
            admin.address = data["address"]
        if "status" in data:
            admin.status = data["status"]

        db.session.commit()

        return (
            jsonify(
                {
                    "status": "success",
                    "message": "Admin details updated successfully",
                    "data": {
                        "id": admin.id,
                        "first_name": admin.first_name,
                        "last_name": admin.last_name,
                        "phone_number": admin.phone_number,
                        "address": admin.address,
                        "status": admin.status,
                    },
                }
            ),
            200,
        )
    except Exception as e:
        db.session.rollback()
        return jsonify({"status": "error", "message": str(e)}), 500
