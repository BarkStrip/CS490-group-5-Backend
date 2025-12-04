# Payment processing, tips
from flask import Blueprint, jsonify, request
from app.extensions import db
from app.models import (
    PayMethod,
    Customers,
    Order,
    OrderItem,
    Cart,
    CartItem,
    LoyaltyAccount,
    LoyaltyProgram,
    LoyaltyTransaction
)
from datetime import datetime
from sqlalchemy import select, delete, update

payments_bp = Blueprint("payments", __name__, url_prefix="/api/payments")


@payments_bp.route("/<int:customer_id>/methods", methods=["GET"])
def get_customer_payment_methods(customer_id):

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
            "card_name": method.card_name,
            "expiration": method.Expiration.isoformat() if method.Expiration else None,
            "is_default": bool(method.is_default),
            "created_at": method.created_at.isoformat() if method.created_at else None,
            "updated_at": method.updated_at.isoformat() if method.updated_at else None,
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
        - card_name (required): Name printed on the card
        - card_name (required): Name printed on the card
        - brand (required): Card brand (e.g., Visa, Mastercard)
        - last4 (required): Last 4 digits of card
        - expiration (required): Card expiration date in MM/YY format
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
    customer = db.session.get(Customers, customer_id)
    if not customer:
        return jsonify({"error": "Customer not found"}), 404

    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "Request body is required"}), 400

        card_name = data.get("card_name")
        brand = data.get("brand")
        last4 = data.get("last4")
        expiration_str = data.get("expiration")
        is_default = data.get("is_default", 0)

        if not card_name or not isinstance(card_name, str) or not card_name.strip():
            return jsonify({"error": "card_name is required"}), 400
        if not brand:
            return jsonify({"error": "brand is required"}), 400
        if not last4:
            return jsonify({"error": "last4 is required"}), 400
        if not expiration_str:
            return jsonify({"error": "expiration is required"}), 400

        if not isinstance(last4, str) or len(last4) != 4 or not last4.isdigit():
            return jsonify({"error": "last4 must be exactly 4 digits"}), 400

        try:
            expiration_date = datetime.strptime(expiration_str, "%m/%y").date()
        except ValueError:
            return jsonify({"error": "expiration must be in MM/YY format"}), 400

        if not isinstance(is_default, int) or is_default not in (0, 1):
            return jsonify({"error": "is_default must be 1 or 0"}), 400

        if is_default:
            existing_defaults = (
                db.session.query(PayMethod)
                .filter(PayMethod.user_id == customer_id, PayMethod.is_default is True)
                .all()
            )
            for method in existing_defaults:
                method.is_default = False

            stmt = (
                update(PayMethod)
                .where(PayMethod.user_id == customer_id, PayMethod.is_default is True)
                .values(is_default=False)
            )
            db.session.execute(stmt)

        new_method = PayMethod(
            user_id=customer_id,
            card_name=card_name,
            brand=brand,
            last4=last4,
            Expiration=expiration_date,
            is_default=is_default,
        )

        db.session.add(new_method)
        db.session.commit()

        created = {
            "id": new_method.id,
            "card_name": new_method.card_name,
            "brand": new_method.brand,
            "last4": new_method.last4,
            "expiration": (
                new_method.Expiration.isoformat() if new_method.Expiration else None
            ),
            "is_default": bool(new_method.is_default),
            "created_at": (
                new_method.created_at.isoformat() if new_method.created_at else None
            ),
            "updated_at": (
                new_method.updated_at.isoformat() if new_method.updated_at else None
            ),
        }

        return jsonify(created), 201

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": "Database error", "details": str(e)}), 500


@payments_bp.route("/<int:customer_id>/methods/<int:method_id>/set-default", methods=["PUT"])
def set_default_payment_method(customer_id, method_id):

    customer = db.session.get(Customers, customer_id)
    if not customer:
        return jsonify({"error": "Customer not found"}), 404

    payment_method = db.session.get(PayMethod, method_id)
    if not payment_method:
        return jsonify({"error": "Payment method not found"}), 404

    if payment_method.user_id != customer_id:
        return (
            jsonify({"error": "Payment method does not belong to this customer"}),
            403,
        )

    try:

        other_methods = (
            db.session.query(PayMethod)
            .filter(
                PayMethod.user_id == customer_id,
                PayMethod.id != method_id,
                PayMethod.is_default == 1,
            )
            .all()
        )

        for method in other_methods:
            method.is_default = 0
        stmt_unset_others = (
            update(PayMethod)
            .where(
                PayMethod.user_id == customer_id,
                PayMethod.id != method_id,
                PayMethod.is_default is True,
            )
            .values(is_default=False)
        )
        db.session.execute(stmt_unset_others)

        payment_method.is_default = 1
        db.session.commit()

        updated = {
            "id": payment_method.id,
            "card_name": payment_method.card_name,
            "brand": payment_method.brand,
            "last4": payment_method.last4,
            "expiration": (
                payment_method.Expiration.isoformat()
                if payment_method.Expiration
                else None
            ),
            "is_default": bool(payment_method.is_default),
            "created_at": (
                payment_method.created_at.isoformat()
                if payment_method.created_at
                else None
            ),
            "updated_at": (
                payment_method.updated_at.isoformat()
                if payment_method.updated_at
                else None
            ),
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
        return (
            jsonify({"error": "Payment method does not belong to this customer"}),
            403,
        )

    try:
        # Delete the payment method
        db.session.delete(payment_method)
        db.session.commit()

        return jsonify({"message": "Payment method deleted successfully"}), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": "Database error", "details": str(e)}), 500


def award_loyalty_points(customer_id, salon_id, order_total):
    print("---- AWARD POINTS START ----")
    print("customer:", customer_id)
    print("salon:", salon_id)
    print("order_total:", order_total)

    program = db.session.scalar(
        select(LoyaltyProgram).where(LoyaltyProgram.salon_id == salon_id)
    )
    print("program found:", program is not None)

    if not program:
        print("NO PROGRAM — EXIT")
        return None

    points_per_dollar = int(program.points_per_dollar or 1)
    print("points_per_dollar:", points_per_dollar)

    earned_points = int(order_total * points_per_dollar)
    print("earned_points:", earned_points)

    account = db.session.scalar(
        select(LoyaltyAccount)
        .where(LoyaltyAccount.user_id == customer_id)
        .where(LoyaltyAccount.salon_id == salon_id)
    )
    print("existing account:", account)

    if not account:
        print("CREATING NEW LOYALTY ACCOUNT")
        account = LoyaltyAccount(
            user_id=customer_id,
            salon_id=salon_id,
            points=earned_points
        )
        db.session.add(account)
        db.session.flush()  # <<< IMPORTANT
        print("new account id after flush:", account.id)
    else:
        print("UPDATING EXISTING ACCOUNT")
        account.points += earned_points

    print("creating transaction now")
    txn = LoyaltyTransaction(
        loyalty_account_id=account.id,
        points_change=earned_points,
        reason=f"Points earned from order (${order_total})"
    )
    db.session.add(txn)

    try:
        db.session.commit()
        print("COMMIT SUCCESSFUL")
    except Exception as e:
        print("COMMIT ERROR:", e)
        db.session.rollback()

    print("---- AWARD POINTS END ----")

    return earned_points


@payments_bp.route("/create_order", methods=["POST"])
def create_order():
    data = request.get_json(force=True)
    customer_id = data.get("customer_id")
    salon_id = data.get("salon_id")

    if not salon_id:
        if len(cart_items) > 0:
            salon_id = cart_items[0].get("salon_id")
        else:
            return jsonify({"error": "salon_id missing and cannot be inferred"}), 400
        
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
        # Create the order
        new_order = Order(
            customer_id=customer_id,
            salon_id=salon_id,
            status="completed",
            subtotal=subtotal,
            tip_amnt=tip_amnt,
            tax_amnt=tax_amnt,
            total_amnt=total_amnt,
            promo_id=promo_id,
        )
        db.session.add(new_order)
        db.session.flush()

        # Create order items
        for item in cart_items:
            order_item = OrderItem(
                order_id=new_order.id,
                kind=item.get("kind"),
                product_id=item.get("product_id"),
                service_id=item.get("service_id"),
                qty=item.get("qty", 1),
                unit_price=item.get("unit_price"),
                line_total=item.get("unit_price") * item.get("qty", 1),
            )
            db.session.add(order_item)

        # Clear the cart (images will remain in cart_item_image temporarily)
        cart_stmt = select(Cart).filter_by(user_id=customer_id)
        customer_cart = db.session.scalar(cart_stmt)

        if customer_cart:
            # Only delete cart items, NOT cart item images
            delete_stmt = delete(CartItem).where(CartItem.cart_id == customer_cart.id)
            db.session.execute(delete_stmt)
            print(
                f"Cleared cart items for customer {customer_id}, but images remain in cart_item_image"
            )

        db.session.commit()

        order_total_for_points = float(subtotal or 0)

        earned = award_loyalty_points(
            customer_id=customer_id,
            salon_id=salon_id,
            order_total=order_total_for_points
        )

        print(f"LOYALTY: Awarded {earned} points to customer {customer_id} (salon {salon_id})")

        return (
            jsonify(
                {"message": "Order created successfully", "order_id": new_order.id}
            ),
            201,
        )

    except Exception as e:
        db.session.rollback()
        print(f"Error creating order: {e}")
        error_response = {"error": "unexpected error", "details": str(e)}
        return error_response, 500
