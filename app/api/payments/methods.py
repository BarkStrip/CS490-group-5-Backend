#Payment processing, tips
from flask import Blueprint, jsonify, request
from app.extensions import db
from app.models import PayMethod, Customers
from datetime import datetime

payments_bp = Blueprint("payments", __name__, url_prefix="/api/payments")


@payments_bp.route("/<int:customer_id>/methods", methods=["GET"])
def get_customer_payment_methods(customer_id):
    """
    GET /api/payments/<customer_id>/methods
    Purpose: Retrieve all payment methods for a specific customer.
    Input: customer_id (integer) from the URL path.

    Behavior:
    - If customer_id is valid:
        → Return a list of all PayMethod objects for that customer,
          ordered by is_default (default methods first), then by creation date.
    - If no payment methods are found:
        → Return an empty list [].
    - If customer_id does not exist:
        → Return a 404 error.
    """

    # Check if customer exists
    customer = db.session.get(Customers, customer_id)

    if not customer:
        return jsonify({"error": "Customer not found"}), 404

    # Query for all payment methods for this customer, ordered by is_default (desc) then created_at (desc)
    payment_methods = db.session.query(PayMethod).filter(
        PayMethod.user_id == customer_id
    ).order_by(PayMethod.is_default.desc(), PayMethod.created_at.desc()).all()

    # Serialize the payment methods
    results = [
        {
            "id": method.id,
            "brand": method.brand,
            "last4": method.last4,
            "expiration": method.expiration.isoformat() if method.expiration else None,
            "is_default": bool(method.is_default),
            "created_at": method.created_at.isoformat() if method.created_at else None,
            "updated_at": method.updated_at.isoformat() if method.updated_at else None
        }
        for method in payment_methods
    ]

    return jsonify(results)


@payments_bp.route("/<int:customer_id>/methods", methods=["POST"])
def create_payment_method(customer_id):
    """
    POST /api/payments/<customer_id>/methods
    Purpose: Create a new payment method for a specific customer.
    Input: JSON body with fields:
        - brand (required): Card brand (e.g., Visa, Mastercard)
        - last4 (required): Last 4 digits of card
        - expiration (required): Card expiration date in YYYY-MM-DD format
        - is_default (optional): 1 (true) or 0 (false - default)

    Behavior:
    - If customer_id does not exist:
        → Return a 404 error.
    - If required fields are missing or invalid:
        → Return a 400 error with details.
    - If is_default is set to 1 and other methods exist:
        → Unset default flag on all other methods for this customer.
    - If creation is successful:
        → Return the new payment method object with 201 status.
    """

    # Check if customer exists
    customer = db.session.get(Customers, customer_id)
    if not customer:
        return jsonify({"error": "Customer not found"}), 404

    try:
        # Get JSON body
        data = request.get_json()
        if not data:
            return jsonify({"error": "Request body is required"}), 400

        brand = data.get("brand")
        last4 = data.get("last4")
        expiration_str = data.get("expiration")
        is_default = data.get("is_default", 0)

        # Validate required fields
        if not brand:
            return jsonify({"error": "brand is required"}), 400
        if not last4:
            return jsonify({"error": "last4 is required"}), 400
        if not expiration_str:
            return jsonify({"error": "expiration is required"}), 400

        # Validate last4 format (should be exactly 4 digits)
        if not isinstance(last4, str) or len(last4) != 4 or not last4.isdigit():
            return jsonify({"error": "last4 must be exactly 4 digits"}), 400

        # Parse and validate expiration date
        try:
            expiration_date = datetime.strptime(expiration_str, "%Y-%m-%d").date()
        except ValueError:
            return jsonify({"error": "expiration must be in YYYY-MM-DD format"}), 400

        # Validate is_default as integer (1 or 0)
        if not isinstance(is_default, int) or is_default not in (0, 1):
            return jsonify({"error": "is_default must be 1 or 0"}), 400

        # If setting this method as default, unset all other defaults for this customer
        if is_default:
            existing_defaults = db.session.query(PayMethod).filter(
                PayMethod.user_id == customer_id,
                PayMethod.is_default == True
            ).all()
            for method in existing_defaults:
                method.is_default = False

        # Create new payment method
        new_method = PayMethod(
            user_id=customer_id,
            brand=brand,
            last4=last4,
            expiration=expiration_date,
            is_default=is_default
        )

        db.session.add(new_method)
        db.session.commit()

        # Return the created payment method
        created = {
            "id": new_method.id,
            "brand": new_method.brand,
            "last4": new_method.last4,
            "expiration": new_method.expiration.isoformat() if new_method.expiration else None,
            "is_default": bool(new_method.is_default),
            "created_at": new_method.created_at.isoformat() if new_method.created_at else None,
            "updated_at": new_method.updated_at.isoformat() if new_method.updated_at else None
        }

        return jsonify(created), 201

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": "Database error", "details": str(e)}), 500


@payments_bp.route("/<int:customer_id>/methods/<int:method_id>/set-default", methods=["PUT"])
def set_default_payment_method(customer_id, method_id):
    """
    PUT /api/payments/<customer_id>/methods/<method_id>/set-default
    Purpose: Set a specific payment method as the default for a customer.
             Automatically removes the default flag from any existing default method.
    Input:
        - customer_id (integer) from the URL path
        - method_id (integer) from the URL path

    Behavior:
    - If customer_id does not exist:
        → Return a 404 error.
    - If method_id does not exist:
        → Return a 404 error.
    - If the payment method does not belong to the customer:
        → Return a 403 error (Forbidden).
    - If successful:
        → Remove is_default from all other methods for this customer
        → Set is_default to 1 for the specified method
        → Return the updated payment method object with 200 status.
    """

    # Check if customer exists
    customer = db.session.get(Customers, customer_id)
    if not customer:
        return jsonify({"error": "Customer not found"}), 404

    # Get the payment method
    payment_method = db.session.get(PayMethod, method_id)
    if not payment_method:
        return jsonify({"error": "Payment method not found"}), 404

    # Verify the payment method belongs to the customer
    if payment_method.user_id != customer_id:
        return jsonify({"error": "Payment method does not belong to this customer"}), 403

    try:
        # Remove is_default from all other payment methods for this customer
        other_methods = db.session.query(PayMethod).filter(
            PayMethod.user_id == customer_id,
            PayMethod.id != method_id,
            PayMethod.is_default == 1
        ).all()

        for method in other_methods:
            method.is_default = 0

        # Set this method as default
        payment_method.is_default = 1

        # Commit changes
        db.session.commit()

        # Return the updated payment method
        updated = {
            "id": payment_method.id,
            "brand": payment_method.brand,
            "last4": payment_method.last4,
            "expiration": payment_method.expiration.isoformat() if payment_method.expiration else None,
            "is_default": int(payment_method.is_default),
            "created_at": payment_method.created_at.isoformat() if payment_method.created_at else None,
            "updated_at": payment_method.updated_at.isoformat() if payment_method.updated_at else None
        }

        return jsonify(updated), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": "Database error", "details": str(e)}), 500
