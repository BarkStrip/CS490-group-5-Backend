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


# -----------------------------------------------------------------------------
# POST /api/cart/add-product
# Purpose:
#   Add a product to the user's cart.
# -----------------------------------------------------------------------------
@cart_bp.route("/add-product", methods=["POST"])
def add_product_to_cart():
    try:
        data = request.get_json(force=True)
        user_id = data.get("user_id")
        product_id = data.get("product_id")
        product_name = data.get("product_name")
        quantity = int(data.get("quantity", 1))
        salon = data.get("salon")
        price = float(data.get("price", 0))

        # --- Validate ---
        if not user_id or not product_id or not product_name:
            return jsonify({
                "status": "error",
                "message": "Missing required fields (user_id, product_id, product_name)"
            }), 400

        # --- Ensure product exists ---
        product = db.session.scalar(select(Product).where(Product.id == product_id))
        if not product:
            return jsonify({
                "status": "error",
                "message": f"Product ID {product_id} not found"
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
                INSERT INTO cart_item (cart_id, kind, product_id, qty, price)
                VALUES (:cart_id, 'product', :product_id, :qty, :price)
            """),
            {"cart_id": cart.id, "product_id": product_id, "qty": quantity, "price": price}
        )
        db.session.commit()

        return jsonify({
            "status": "success",
            "message": "Product added to cart successfully",
            "cart_item": {
                "user_id": user_id,
                "product_id": product_id,
                "product_name": product_name,
                "quantity": quantity,
                "salon": salon,
                "price": price
            }
        }), 201

    except IntegrityError as e:
        db.session.rollback()
        return jsonify({"status": "error", "message": str(e.orig)}), 400
    except Exception as e:
        db.session.rollback()
        return jsonify({"status": "error", "message": str(e)}), 500


from flask import Blueprint, jsonify
from sqlalchemy import text, select
from ..extensions import db
from ..models import Cart

cart_bp = Blueprint("cart", __name__, url_prefix="/api/cart")

# ---------------------------------------------------------------------------
# GET /api/cart/<user_id>
# Purpose:
#   Fetch all items in the given user's cart, including both services and products.
#
# Input:
#   URL parameter: user_id
#
# Logic:
#   1. Find cart by user_id.
#   2. Fetch all cart_item records linked to this cart.
#   3. For each record, join with either service or product to fetch details.
# ---------------------------------------------------------------------------
@cart_bp.route("/<int:user_id>", methods=["GET"])
def get_cart(user_id):
    try:
        # --- Find the user's cart ---
        cart = db.session.scalar(select(Cart).where(Cart.user_id == user_id))
        if not cart:
            return jsonify({
                "status": "error",
                "message": f"No cart found for user_id {user_id}"
            }), 404

        # --- Fetch both service and product items ---
        query = text("""
            SELECT 
                ci.id AS item_id,
                ci.kind AS item_type,
                ci.qty AS quantity,
                ci.price AS item_price,
                CASE 
                    WHEN ci.kind = 'service' THEN s.id
                    WHEN ci.kind = 'product' THEN p.id
                END AS item_ref_id,
                CASE 
                    WHEN ci.kind = 'service' THEN s.name
                    WHEN ci.kind = 'product' THEN p.name
                END AS item_name,
                CASE 
                    WHEN ci.kind = 'product' THEN p.salon
                    ELSE NULL
                END AS salon_name
            FROM cart_item ci
            LEFT JOIN service s ON ci.service_id = s.id
            LEFT JOIN product p ON ci.product_id = p.id
            WHERE ci.cart_id = :cart_id
        """)

        result = db.session.execute(query, {"cart_id": cart.id})
        items = [dict(row._mapping) for row in result]

        # --- Handle empty cart ---
        if not items:
            return jsonify({
                "status": "success",
                "message": "Cart is empty",
                "cart_id": cart.id,
                "items": []
            }), 200

        # --- Return response ---
        return jsonify({
            "status": "success",
            "message": "Cart details fetched successfully",
            "cart_id": cart.id,
            "user_id": user_id,
            "items": items
        }), 200

    except Exception as e:
        return jsonify({
            "status": "error",
            "message": "Internal server error",
            "details": str(e)
        }), 500
