from flask import Blueprint, request, jsonify
from sqlalchemy import select
from ...extensions import db
from ...models import Customers, AuthUser

details_bp = Blueprint("customer_details", __name__, url_prefix="/api/customer/details")


@details_bp.route("/<int:customer_id>", methods=["GET"])
def get_customer_details(customer_id):
    """
    Get customer details by customer ID
    ---
    tags:
      - Customer Details
    parameters:
      - in: path
        name: customer_id
        type: integer
        required: true
        description: Customer ID
    responses:
      200:
        description: Customer details retrieved successfully
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
                email:
                  type: string
                date_of_birth:
                  type: string
                  format: date
                age:
                  type: integer
      404:
        description: Customer not found
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
        customer = db.session.get(Customers, customer_id)
        if not customer:
            return jsonify({"status": "error", "message": "Customer not found"}), 404

        user = db.session.get(AuthUser, customer.user_id)
        email = user.email if user else None

        return (
            jsonify(
                {
                    "status": "success",
                    "data": {
                        "id": customer.id,
                        "first_name": customer.first_name,
                        "last_name": customer.last_name,
                        "phone_number": customer.phone_number,
                        "address": customer.address,
                        "email": email,
                        "date_of_birth": customer.date_of_birth.isoformat() if customer.date_of_birth else None,
                        "age": customer.age,
                    },
                }
            ),
            200,
        )
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@details_bp.route("/<int:customer_id>", methods=["PUT"])
def edit_customer_details(customer_id):
    """
    Edit customer details (first_name, last_name, phone_number, address)
    ---
    tags:
      - Customer Details
    parameters:
      - in: path
        name: customer_id
        type: integer
        required: true
        description: Customer ID
      - in: body
        name: body
        required: true
        schema:
          type: object
          properties:
            first_name:
              type: string
              description: Customer first name (optional)
            last_name:
              type: string
              description: Customer last name (optional)
            phone_number:
              type: string
              description: Customer phone number (optional)
            address:
              type: string
              description: Customer address (optional)
    responses:
      200:
        description: Customer details updated successfully
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
        description: Customer not found
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

        customer = db.session.get(Customers, customer_id)
        if not customer:
            return jsonify({"status": "error", "message": "Customer not found"}), 404

        # Update optional fields if provided
        if "first_name" in data:
            customer.first_name = data["first_name"]
        if "last_name" in data:
            customer.last_name = data["last_name"]
        if "phone_number" in data:
            customer.phone_number = data["phone_number"]
        if "address" in data:
            customer.address = data["address"]

        db.session.commit()

        return (
            jsonify(
                {
                    "status": "success",
                    "message": "Customer details updated successfully",
                    "data": {
                        "id": customer.id,
                        "first_name": customer.first_name,
                        "last_name": customer.last_name,
                        "phone_number": customer.phone_number,
                        "address": customer.address,
                    },
                }
            ),
            200,
        )
    except Exception as e:
        db.session.rollback()
        return jsonify({"status": "error", "message": str(e)}), 500
