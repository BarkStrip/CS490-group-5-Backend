#Payment processing, tips
from flask import Blueprint, jsonify, request
from app.extensions import db
from app.models import PayMethod, Customers, Order, OrderItem, Cart, CartItem
from datetime import datetime
from sqlalchemy import select, delete, update
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

    # Check if customer exists (db.session.get is 2.0 compatible)
    customer = db.session.get(Customers, customer_id)

    if not customer:
        return jsonify({"error": "Customer not found"}), 404

    stmt = (
        select(PayMethod)
        .where(PayMethod.user_id == customer_id)
        .order_by(PayMethod.is_default.desc(), PayMethod.created_at.desc())
    )
    
    payment_methods = db.session.scalars(stmt).all()

    results = [
        {
            "id": method.id,
            "brand": method.brand,
            "last4": method.last4,
            "expiration": method.Expiration.isoformat() if method.Expiration else None,
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
            
    
            stmt = (
                update(PayMethod)
                .where(
                    PayMethod.user_id == customer_id,
                    PayMethod.is_default == True
                )
                .values(is_default=False)
            )
            db.session.execute(stmt)


      
        new_method = PayMethod(
            user_id=customer_id,
            brand=brand,
            last4=last4,
            Expiration=expiration_date,
            is_default=is_default
        )

        db.session.add(new_method)
        db.session.commit()

        created = {
            "id": new_method.id,
            "brand": new_method.brand,
            "last4": new_method.last4,
            "expiration": new_method.Expiration.isoformat() if new_method.Expiration else None,
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
   
        other_methods = db.session.query(PayMethod).filter(
            PayMethod.user_id == customer_id,
            PayMethod.id != method_id,
            PayMethod.is_default == 1
        ).all()
        
        for method in other_methods:
            method.is_default = 0
        stmt_unset_others = (
            update(PayMethod)
            .where(
                PayMethod.user_id == customer_id,
                PayMethod.id != method_id,
                PayMethod.is_default == True
            )
            .values(is_default=False)
        )
        db.session.execute(stmt_unset_others)


        payment_method.is_default = 1

        db.session.commit()

        updated = {
            "id": payment_method.id,
            "brand": payment_method.brand,
            "last4": payment_method.last4,
            "expiration": payment_method.Expiration.isoformat() if payment_method.Expiration else None,
            "is_default": bool(payment_method.is_default),
            "created_at": payment_method.created_at.isoformat() if payment_method.created_at else None,
            "updated_at": payment_method.updated_at.isoformat() if payment_method.updated_at else None
        }

        return jsonify(updated), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": "Database error", "details": str(e)}), 500

@payments_bp.route("/<int:customer_id>/methods/<int:method_id>", methods=["DELETE"])
def delete_payment_method(customer_id, method_id):
    """
    DELETE /api/payments/<customer_id>/methods/<int:method_id>
    Purpose: Delete a specific payment method for a customer.
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
        → Delete the payment method from the database.
        → Return a 200 status with a success message.
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
        # Delete the payment method
        db.session.delete(payment_method)
        db.session.commit()

        return jsonify({"message": "Payment method deleted successfully"}), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": "Database error", "details": str(e)}), 500

@payments_bp.route("/create_order", methods=["POST"])
def create_order():  

    data = request.get_json(force=True)
    customer_id = data.get("customer_id")
    salon_id = data.get("salon_id")
    subtotal = data.get("subtotal")
    tip_amnt = data.get("tip_amnt", 0)
    tax_amnt = data.get("tax_amnt", 0)
    total_amnt = data.get("total_amnt")
    promo_id = data.get("promo_id", 0)
    cart_items = data.get("cart_items", [])

    if not data:
        return jsonify({"error": "No JSON body received"}), 400
    
    required_fields = ["customer_id", "cart_items", "total_amnt"]
    for field in required_fields:
        if field not in data:
            return jsonify({"error": f"Missing required field: {field}"}), 400

    if not customer_id or not cart_items:
        return jsonify({"error": "Missing required fields"}), 400
        
    try: 
        new_order = Order(
            customer_id=customer_id,
            salon_id=salon_id,
            status="completed", 
            subtotal=subtotal,
            tip_amnt=tip_amnt,
            tax_amnt=tax_amnt,
            total_amnt=total_amnt,
            promo_id=promo_id
        )
        db.session.add(new_order)
        db.session.flush()

        for item in cart_items:
            order_item = OrderItem(
                order_id=new_order.id,
                kind=item.get("kind"),
                product_id=item.get("product_id"),
                service_id=item.get("service_id"),
                qty=item.get("qty", 1),
                unit_price=item.get("unit_price"),
                line_total=item.get("unit_price") * item.get("qty", 1)
            )
            db.session.add(order_item)

        cart_stmt = select(Cart).filter_by(user_id=customer_id)
        customer_cart = db.session.scalar(cart_stmt)

        if customer_cart: 
            delete_stmt = delete(CartItem).where(CartItem.cart_id == customer_cart.id)
            db.session.execute(delete_stmt)

        db.session.commit()

        return jsonify({
            "message": "Order created successfully",
            "order_id": new_order.id
        }), 201
    
    except Exception as e: 
        db.session.rollback()
        print(f"Error creating order: {e}")
        error_response = {"error": "unexpected error", "details": str(e)}
        return error_response, 500