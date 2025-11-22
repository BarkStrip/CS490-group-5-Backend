from flask import Blueprint, request, jsonify
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from ..extensions import db
from ..models import (
    Cart,
    Service,
    Product,
    CartItem,
    Customers,
    AppointmentImage,
)

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
        customer_id = data.get("user_id")
        service_id = data.get("service_id")
        quantity = int(data.get("quantity", 1))
        appt_date = data.get("appt_date")
        appt_time = data.get("appt_time")
        stylist = data.get("stylist")
        pictures = data.get("pictures", [])
        notes = data.get("notes")
        stylist_id = data.get("stylist_id")
        # --- Validate ---
        if not customer_id or not service_id:
            return (
                jsonify(
                    {
                        "status": "error",
                        "message": "Missing required fields (user_id, service_id)",
                    }
                ),
                400,
            )

        # --- Ensure service exists ---
        customer = db.session.scalar(
            select(Customers).where(Customers.id == customer_id)
        )
        if not customer:
            return jsonify({"status": "error", "message": "Customer not found"}), 404

        # --- Ensure service exists and is active ---
        service = db.session.scalar(
            select(Service).where(Service.id == service_id, Service.is_active.is_(True))
        )
        if not service:
            return (
                jsonify(
                    {
                        "status": "error",
                        "message": f"Service ID {service_id} not found or inactive",
                    }
                ),
                404,
            )

        # --- Create / get user's cart ---
        cart = db.session.scalar(select(Cart).where(Cart.user_id == customer.id))
        if not cart:
            cart = Cart(user_id=customer.id)
            db.session.add(cart)
            db.session.flush()
        # --- Prepare appointment datetime if provided ---
        start_datetime = None
        end_datetime = None
        if appt_date and appt_time:
            from datetime import datetime, timedelta

            try:
                # Combine date and time
                start_datetime = datetime.strptime(
                    f"{appt_date} {appt_time}", "%Y-%m-%d %H:%M"
                )
                # Calculate end time based on service duration
                end_datetime = start_datetime + timedelta(minutes=service.duration)
            except ValueError:
                return (
                    jsonify(
                        {
                            "status": "error",
                            "message": "Invalid date/time format. Use YYYY-MM-DD for date and HH:MM for time",
                        }
                    ),
                    400,
                )

        # --- Insert into cart_item ---
        cart_item = CartItem(
            cart_id=cart.id,
            kind="service",
            service_id=service_id,
            qty=quantity,
            price=service.price,
            start_at=start_datetime,
            end_at=end_datetime,
            notes=notes,
            stylist_id=stylist_id,
        )
        db.session.add(cart_item)
        db.session.flush()  # Get cart_item.id before using it

        # --- Insert iamge into AppointmentImage table ---
        created_images = []
        if pictures:
            for picture_url in pictures:
                appointment_image = AppointmentImage(
                    url=picture_url,
                    cart_item_id=cart_item.id,
                    appointment_id=None,  # Will be set during checkout
                )
                db.session.add(appointment_image)
                created_images.append(picture_url)

        db.session.commit()

        return (
            jsonify(
                {
                    "status": "success",
                    "message": "Service added to cart successfully",
                    "cart_item": {
                        "cart_item_id": cart_item.id,
                        "customer_id": customer_id,
                        "service_id": service_id,
                        "quantity": quantity,
                        "price": float(service.price),
                        "start_at": (
                            start_datetime.isoformat() if start_datetime else None
                        ),
                        "end_at": end_datetime.isoformat() if end_datetime else None,
                        "notes": notes,
                        "pictures": created_images,
                        "stylist_id": stylist_id,  # Note: Still not stored in database
                    },
                }
            ),
            201,
        )

    except IntegrityError as e:
        db.session.rollback()
        return jsonify({"status": "error", "message": str(e.orig)}), 400
    except ValueError as e:
        db.session.rollback()
        return jsonify({"status": "error", "message": f"Invalid data: {str(e)}"}), 400
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
        quantity = int(data.get("quantity", 1))

        # --- Validate ---
        if not user_id or not product_id:
            return (
                jsonify(
                    {
                        "status": "error",
                        "message": "Missing required fields (user_id, product_id)",
                    }
                ),
                400,
            )

        # --- Ensure product exists and fetch price from database ---
        product = db.session.scalar(select(Product).where(Product.id == product_id))
        if not product:
            return (
                jsonify(
                    {"status": "error", "message": f"Product ID {product_id} not found"}
                ),
                404,
            )

        # --- Create / get user's cart ---
        cart = db.session.scalar(select(Cart).where(Cart.user_id == user_id))
        if not cart:
            cart = Cart(user_id=user_id)
            db.session.add(cart)
            db.session.commit()

        # --- Insert into cart_item with auto-fetched price ---
        db.session.execute(
            text(
                """
                INSERT INTO cart_item (cart_id, kind, product_id, qty, price)
                VALUES (:cart_id, 'product', :product_id, :qty, :price)
            """
            ),
            {
                "cart_id": cart.id,
                "product_id": product_id,
                "qty": quantity,
                "price": float(product.price),
            },
        )
        db.session.commit()

        return (
            jsonify(
                {
                    "status": "success",
                    "message": "Product added to cart successfully",
                    "cart_item": {
                        "user_id": user_id,
                        "product_id": product_id,
                        "quantity": quantity,
                        "price": float(product.price),
                    },
                }
            ),
            201,
        )

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
    """
    try:
        from sqlalchemy.orm import joinedload

        # --- Find user's cart ---
        cart = db.session.scalar(
            select(Cart)
            .where(Cart.user_id == user_id)
            .options(
                joinedload(Cart.cart_item)
                .joinedload(CartItem.service)
                .joinedload(Service.salon),
                joinedload(Cart.cart_item)
                .joinedload(CartItem.product)
                .joinedload(Product.salon),
            )
        )

        if not cart:
            return (
                jsonify(
                    {
                        "status": "error",
                        "message": f"No cart found for user_id {user_id}",
                    }
                ),
                404,
            )

        # --- Build response with all details ---
        items = []
        for cart_item in cart.cart_item:
            item_data = {
                "item_id": cart_item.id,
                "item_type": cart_item.kind,
                "quantity": cart_item.qty,
                "item_price": float(cart_item.price) if cart_item.price else None,
                "start_at": (
                    cart_item.start_at.isoformat() if cart_item.start_at else None
                ),
                "end_at": cart_item.end_at.isoformat() if cart_item.end_at else None,
                "notes": cart_item.notes,
            }

            if cart_item.service:
                item_data["service_id"] = cart_item.service.id
                item_data["service_name"] = cart_item.service.name
                item_data["service_price"] = float(cart_item.service.price)
                item_data["service_duration"] = cart_item.service.duration
                item_data["service_salon_id"] = cart_item.service.salon_id
                item_data["service_salon_name"] = (
                    cart_item.service.salon.name if cart_item.service.salon else None
                )

            if cart_item.product:
                item_data["product_id"] = cart_item.product.id
                item_data["product_name"] = cart_item.product.name
                item_data["product_price"] = float(cart_item.product.price)
                item_data["product_stock"] = cart_item.product.stock_qty
                item_data["product_salon_id"] = cart_item.product.salon_id
                item_data["product_salon_name"] = (
                    cart_item.product.salon.name if cart_item.product.salon else None
                )

            # Add associated appointment images
            images = db.session.scalars(
                select(AppointmentImage).where(
                    AppointmentImage.cart_item_id == cart_item.id
                )
            ).all()
            item_data["images"] = [img.url for img in images]

            items.append(item_data)

        return (
            jsonify(
                {
                    "status": "success",
                    "cart_id": cart.id,
                    "user_id": user_id,
                    "total_items": len(items),
                    "items": items,
                }
            ),
            200,
        )

    except Exception as e:
        db.session.rollback()
        return (
            jsonify(
                {
                    "status": "error",
                    "message": "Internal server error",
                    "details": str(e),
                }
            ),
            500,
        )


# -------------------------------------------------------------------------
# PUT /api/cart/update-service/<service_id>
# Purpose: Edit an existing salon service (update name, price, duration, etc.)
# -------------------------------------------------------------------------
@cart_bp.route("/update-service/<int:service_id>", methods=["PUT"])
def update_salon_service(service_id):
    """
    Update an existing salon service.
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

        # --- Fetch service ---
        service = db.session.get(Service, service_id)
        if not service:
            return (
                jsonify(
                    {"status": "error", "message": f"Service ID {service_id} not found"}
                ),
                404,
            )

        # --- Track updated fields ---
        updated_fields = {}

        # --- Update fields dynamically ---
        if "name" in data and data.get("name"):
            service.name = data["name"]
            updated_fields["name"] = data["name"]

        if "price" in data and data.get("price") is not None:
            service.price = float(data["price"])
            updated_fields["price"] = float(data["price"])

        if "duration" in data and data.get("duration") is not None:
            service.duration = int(data["duration"])
            updated_fields["duration"] = int(data["duration"])

        if "salon_id" in data and data.get("salon_id") is not None:
            service.salon_id = int(data["salon_id"])
            updated_fields["salon_id"] = int(data["salon_id"])

        if "is_active" in data and data.get("is_active") is not None:
            service.is_active = bool(data["is_active"])
            updated_fields["is_active"] = bool(data["is_active"])

        if "icon_url" in data:
            service.icon_url = data.get("icon_url")
            updated_fields["icon_url"] = data.get("icon_url")

        # --- Check if any updates were provided ---
        if not updated_fields:
            return (
                jsonify(
                    {"status": "error", "message": "No valid update fields provided"}
                ),
                400,
            )

        # --- Commit changes ---
        db.session.commit()

        return (
            jsonify(
                {
                    "status": "success",
                    "message": f"Service ID {service_id} updated successfully",
                    "data": {
                        "id": service.id,
                        "salon_id": service.salon_id,
                        "name": service.name,
                        "price": float(service.price),
                        "duration": service.duration,
                        "is_active": bool(service.is_active),
                        "icon_url": service.icon_url,
                    },
                    "updated_fields": updated_fields,
                }
            ),
            200,
        )

    except IntegrityError as e:
        db.session.rollback()
        return (
            jsonify(
                {
                    "status": "error",
                    "message": "Database integrity error",
                    "details": str(e.orig),
                }
            ),
            400,
        )
    except ValueError as e:
        db.session.rollback()
        return (
            jsonify(
                {
                    "status": "error",
                    "message": "Invalid data type provided",
                    "details": str(e),
                }
            ),
            400,
        )
    except Exception as e:
        db.session.rollback()
        return (
            jsonify(
                {
                    "status": "error",
                    "message": "Internal server error",
                    "details": str(e),
                }
            ),
            500,
        )


# -------------------------------------------------------------------------
# PUT /api/cart/update-product/<product_id>
# Purpose: Edit an existing salon product (update name, price, stock, etc.)
# -------------------------------------------------------------------------
@cart_bp.route("/update-product/<int:product_id>", methods=["PUT"])
def update_salon_product(product_id):
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

        # --- Fetch product ---
        product = db.session.get(Product, product_id)
        if not product:
            return (
                jsonify(
                    {"status": "error", "message": f"Product ID {product_id} not found"}
                ),
                404,
            )

        # --- Track updated fields ---
        updated_fields = {}

        # --- Update fields dynamically ---
        if "name" in data and data.get("name"):
            product.name = data["name"]
            updated_fields["name"] = data["name"]

        if "description" in data:
            product.description = data.get("description")
            updated_fields["description"] = data.get("description")

        if "price" in data and data.get("price") is not None:
            product.price = float(data["price"])
            updated_fields["price"] = float(data["price"])

        if "stock_qty" in data and data.get("stock_qty") is not None:
            product.stock_qty = int(data["stock_qty"])
            updated_fields["stock_qty"] = int(data["stock_qty"])

        if "salon_id" in data and data.get("salon_id") is not None:
            product.salon_id = int(data["salon_id"])
            updated_fields["salon_id"] = int(data["salon_id"])

        if "is_active" in data and data.get("is_active") is not None:
            product.is_active = bool(data["is_active"])
            updated_fields["is_active"] = bool(data["is_active"])

        if "image_url" in data:
            product.image_url = data.get("image_url")
            updated_fields["image_url"] = data.get("image_url")

        # --- Check if any updates were provided ---
        if not updated_fields:
            return (
                jsonify(
                    {"status": "error", "message": "No valid update fields provided"}
                ),
                400,
            )

        # --- Commit changes ---
        db.session.commit()

        return (
            jsonify(
                {
                    "status": "success",
                    "message": f"Product ID {product_id} updated successfully",
                    "data": {
                        "id": product.id,
                        "salon_id": product.salon_id,
                        "name": product.name,
                        "description": product.description,
                        "price": float(product.price),
                        "stock_qty": product.stock_qty,
                        "is_active": bool(product.is_active),
                        "image_url": product.image_url,
                    },
                    "updated_fields": updated_fields,
                }
            ),
            200,
        )

    except IntegrityError as e:
        db.session.rollback()
        return (
            jsonify(
                {
                    "status": "error",
                    "message": "Database integrity error",
                    "details": str(e.orig),
                }
            ),
            400,
        )
    except ValueError as e:
        db.session.rollback()
        return (
            jsonify(
                {
                    "status": "error",
                    "message": "Invalid data type provided",
                    "details": str(e),
                }
            ),
            400,
        )
    except Exception as e:
        db.session.rollback()
        return (
            jsonify(
                {
                    "status": "error",
                    "message": "Internal server error",
                    "details": str(e),
                }
            ),
            500,
        )


@cart_bp.route("/delete-cart-item", methods=["DELETE"])
def delete_cart_item():
    """
    Delete a service or product from a user's cart.
    """

    cart_id = request.args.get("cart_id", type=int)
    item_id = request.args.get("item_id", type=int)
    kind = request.args.get("kind")  # product or service

    if not all([cart_id, item_id, kind]):
        return jsonify({"error": "cart_id, item_id, and kind are required"}), 400

    try:

        if kind == "product":
            cart_item = (
                db.session.query(CartItem)
                .filter_by(cart_id=cart_id, product_id=item_id)
                .first()
            )
        elif kind == "service":
            cart_item = (
                db.session.query(CartItem)
                .filter_by(cart_id=cart_id, service_id=item_id)
                .first()
            )
        else:
            return (
                jsonify({"error": "Invalid kind. Must be 'product' or 'service'"}),
                400,
            )

        if not cart_item:
            return jsonify({"error": "Item not found in cart"}), 404

        db.session.delete(cart_item)
        db.session.commit()

        return jsonify({"message": "Item Deleted Successfully"})

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500


@cart_bp.route("/update-item-quantity", methods=["PATCH"])
def update_cart_item_quantity():
    """
    Updates the quantity of a single item in the cart
    based on cart_id, item_id (product_id), and kind.
    """
    try:
        data = request.get_json(force=True)
        cart_id = data.get("cart_id")
        item_id = data.get("item_id")
        kind = data.get("kind")
        new_quantity = data.get("quantity")

        if not all([cart_id, item_id, kind, new_quantity is not None]):
            return (
                jsonify(
                    {
                        "status": "error",
                        "message": "Missing required fields: cart_id, item_id, kind, quantity",
                    }
                ),
                400,
            )

        if kind != "product":
            return (
                jsonify(
                    {
                        "status": "error",
                        "message": "This endpoint only supports updating 'product' quantities.",
                    }
                ),
                400,
            )

        try:
            new_quantity = int(new_quantity)
            if new_quantity <= 0:
                return (
                    jsonify(
                        {
                            "status": "error",
                            "message": "Quantity must be a positive integer. To remove, use the delete endpoint.",
                        }
                    ),
                    400,
                )
        except ValueError:
            return (
                jsonify(
                    {"status": "error", "message": "Quantity must be a valid integer."}
                ),
                400,
            )

        cart_item = db.session.scalar(
            select(CartItem).where(
                CartItem.cart_id == cart_id,
                CartItem.product_id == item_id,
                CartItem.kind == "product",
            )
        )

        if not cart_item:
            return (
                jsonify(
                    {
                        "status": "error",
                        "message": f"No product with ID {item_id} found in cart {cart_id}",
                    }
                ),
                404,
            )

        product = db.session.get(Product, item_id)
        if not product:
            return (
                jsonify(
                    {
                        "status": "error",
                        "message": f"Associated product (ID: {item_id}) not found. Cannot validate stock.",
                    }
                ),
                404,
            )

        if new_quantity > product.stock_qty:
            return (
                jsonify(
                    {
                        "status": "error",
                        "message": f"Not enough stock for {product.name}. Available: {product.stock_qty}",
                    }
                ),
                409,
            )

        cart_item.qty = new_quantity

        db.session.commit()

        return (
            jsonify(
                {
                    "status": "success",
                    "message": f"Quantity for product {item_id} updated to {new_quantity}",
                    "cart_item": {
                        "cart_item_id": cart_item.id,
                        "kind": cart_item.kind,
                        "product_id": cart_item.product_id,
                        "quantity": cart_item.qty,
                        "unit_price": float(cart_item.price),
                    },
                }
            ),
            200,
        )

    except IntegrityError as e:
        db.session.rollback()
        return jsonify({"status": "error", "message": str(e.orig)}), 400
    except Exception as e:
        db.session.rollback()
        return (
            jsonify(
                {
                    "status": "error",
                    "message": "Internal server error",
                    "details": str(e),
                }
            ),
            500,
        )
