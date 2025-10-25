from flask import Blueprint, request, jsonify
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from ..extensions import db
from ..models import Cart, Service, Product

cart_bp = Blueprint("cart", __name__, url_prefix="/api/cart")

# -----------------------------------------------------------------------------
# POST /api/cart/add-service
# Purpose:
#   Add a salon service (appointment) to the user's cart.
# -----------------------------------------------------------------------------
@cart_bp.route("/add-service", methods=["POST"])
def add_service_to_cart():
    try:
        data = request.get_json(force=True)
        user_id = data.get("user_id")
        service_id = data.get("service_id")
        quantity = int(data.get("quantity", 1))
        appt_date = data.get("appt_date")
        appt_time = data.get("appt_time")
        stylist = data.get("stylist")
        pictures = data.get("pictures", [])
        notes = data.get("notes")

        # --- Validate ---
        if not user_id or not service_id:
            return jsonify({
                "status": "error",
                "message": "Missing required fields (user_id, service_id)"
            }), 400

        # --- Ensure service exists ---
        service = db.session.scalar(select(Service).where(Service.id == service_id))
        if not service:
            return jsonify({
                "status": "error",
                "message": f"Service ID {service_id} not found"
            }), 404

        # --- Create / get user's cart ---
        cart = db.session.scalar(select(Cart).where(Cart.user_id == user_id))
        if not cart:
            cart = Cart(user_id=user_id)
            db.session.add(cart)
            db.session.commit()

        # --- Insert into cart_item ---
        db.session.execute(
            text("""
                INSERT INTO cart_item (cart_id, kind, service_id, qty, price)
                VALUES (:cart_id, 'service', :service_id, :qty, :price)
            """),
            {"cart_id": cart.id, "service_id": service_id, "qty": quantity, "price": service.price}
        )
        db.session.commit()

        return jsonify({
            "status": "success",
            "message": "Service added to cart successfully",
            "cart_item": {
                "user_id": user_id,
                "service_id": service_id,
                "quantity": quantity,
                "stylist": stylist,
                "appt_date": appt_date,
                "appt_time": appt_time,
                "notes": notes,
                "pictures": pictures
            }
        }), 201

    except IntegrityError as e:
        db.session.rollback()
        return jsonify({"status": "error", "message": str(e.orig)}), 400
    except Exception as e:
        db.session.rollback()
        return jsonify({"status": "error", "message": str(e)}), 500


