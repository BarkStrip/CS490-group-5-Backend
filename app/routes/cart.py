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



@cart_bp.route("/<int:user_id>", methods=["GET"])
def get_cart_details(user_id):
    """
    Fetch detailed cart info for a given user_id.
    Includes both service and product items with joined salon details.
    """
    try:
        # Step 1: Find user's cart
        cart = db.session.execute(
            text("SELECT id FROM cart WHERE user_id = :uid"),
            {"uid": user_id}
        ).fetchone()

        if not cart:
            return jsonify({"status": "error", "message": f"No cart found for user_id {user_id}"}), 404

        # Step 2: Query all cart items with joined data
        query = text("""
            SELECT 
                ci.id AS item_id,
                ci.kind AS item_type,
                ci.qty AS quantity,
                ci.price AS item_price,

                -- Service details
                s.id AS service_id,
                s.name AS service_name,
                s.price AS service_price,
                s.duration AS service_duration,
                s.salon_id AS service_salon_id,
                sl1.name AS service_salon_name,

                -- Product details
                p.id AS product_id,
                p.name AS product_name,
                p.price AS product_price,
                p.stock_qty AS product_stock,
                p.salon_id AS product_salon_id,
                sl2.name AS product_salon_name

            FROM cart_item ci
            LEFT JOIN service s ON ci.service_id = s.id
            LEFT JOIN salon sl1 ON s.salon_id = sl1.id
            LEFT JOIN product p ON ci.product_id = p.id
            LEFT JOIN salon sl2 ON p.salon_id = sl2.id
            WHERE ci.cart_id = :cart_id
        """)

        result = db.session.execute(query, {"cart_id": cart.id})
        items = [dict(row._mapping) for row in result]

        return jsonify({
            "status": "success",
            "cart_id": cart.id,
            "user_id": user_id,
            "total_items": len(items),
            "items": items
        }), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({
            "status": "error",
            "message": "Internal server error",
            "details": str(e)
        }), 500


@cart_bp.route("/add-salon-item", methods=["POST"])
def add_salon_item():
    """
    Add a new service or product to a salon's offerings.
    Request JSON must include:
      - type: "service" or "product"
      - salon_id: int
      - name: str
      - price: float
      - duration (for service only)
      - stock_qty (for product only)
      - description (optional, for product only)
    """
    try:
        data = request.get_json(force=True)
        item_type = data.get("type")
        salon_id = data.get("salon_id")
        name = data.get("name")
        price = float(data.get("price", 0))
        duration = data.get("duration")
        stock_qty = data.get("stock_qty", 0)
        description = data.get("description")

        # --- Validate ---
        if not item_type or not salon_id or not name:
            return jsonify({
                "status": "error",
                "message": "Missing required fields: type, salon_id, or name"
            }), 400

        # --- Handle adding a SERVICE ---
        if item_type.lower() == "service":
            db.session.execute(
                text("""
                    INSERT INTO service (name, duration, price, salon_id)
                    VALUES (:name, :duration, :price, :salon_id)
                """),
                {"name": name, "duration": duration, "price": price, "salon_id": salon_id}
            )
            db.session.commit()

            return jsonify({
                "status": "success",
                "message": "New service added to salon successfully",
                "data": {
                    "type": "service",
                    "salon_id": salon_id,
                    "name": name,
                    "price": price,
                    "duration": duration
                }
            }), 201

        # --- Handle adding a PRODUCT ---
        elif item_type.lower() == "product":
            db.session.execute(
                text("""
                    INSERT INTO product (name, description, price, stock_qty, salon_id)
                    VALUES (:name, :description, :price, :stock_qty, :salon_id)
                """),
                {
                    "name": name,
                    "description": description,
                    "price": price,
                    "stock_qty": stock_qty,
                    "salon_id": salon_id
                }
            )
            db.session.commit()

            return jsonify({
                "status": "success",
                "message": "New product added to salon successfully",
                "data": {
                    "type": "product",
                    "salon_id": salon_id,
                    "name": name,
                    "price": price,
                    "stock_qty": stock_qty,
                    "description": description
                }
            }), 201

        else:
            return jsonify({
                "status": "error",
                "message": "Invalid type. Must be 'service' or 'product'."
            }), 400

    except IntegrityError as e:
        db.session.rollback()
        return jsonify({
            "status": "error",
            "message": str(e.orig)
        }), 400
    except Exception as e:
        db.session.rollback()
        return jsonify({
            "status": "error",
            "message": "Internal server error",
            "details": str(e)
        }), 500
