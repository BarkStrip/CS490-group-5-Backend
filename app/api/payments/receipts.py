# Invoices, refunds, tracking
from flask import Blueprint, jsonify
from ...extensions import db
from ...models import (
    Salon,
    Order,
    Customers,
    OrderItem,
    Booking,
    Appointment,
    Service,
    Product,
)
from sqlalchemy import select, or_
from sqlalchemy.orm import joinedload, selectinload

receipts_bp = Blueprint("payment", __name__, url_prefix="/api/receipts")


@receipts_bp.route("/salon/<int:salon_id>/transactions", methods=["GET"])
def get_salon_transactions(salon_id):
    """
    Returns all transactions for a given salon id, including
    customer info, item details, and an assumed 'paid' status.

    IMPORTANT ASSUMPTION:
    - Any Order that has OrderItem rows is treated as PAID
      (we no longer rely on the Payment table here).
    """
    try:
        salon = db.session.get(Salon, salon_id)
        if not salon:
            return jsonify({
                "status": "error",
                "message": f"Salon with id {salon_id} not found",
            }), 404

        # Build transactions from orders + items instead of Payment
        query = (
            select(Order)
            .join(OrderItem, OrderItem.order_id == Order.id)
            .outerjoin(Service, Service.id == OrderItem.service_id)
            .outerjoin(Product, Product.id == OrderItem.product_id)
            .where(
                or_(
                    Order.salon_id == salon_id,
                    Service.salon_id == salon_id,
                    Product.salon_id == salon_id,
                )
            )
            .options(
                joinedload(Order.customer).joinedload(Customers.user),
                selectinload(Order.order_item).options(
                    joinedload(OrderItem.service),
                    joinedload(OrderItem.product),
                    selectinload(OrderItem.booking).options(
                        joinedload(Booking.appointment).joinedload(
                            Appointment.employee
                        )
                    ),
                ),
            )
            .order_by(Order.created_at.desc())
        )

        orders = db.session.scalars(query).unique().all()

        transactions_list = []

        for order in orders:
            if not order.customer or not order.customer.user:
                continue

            customer = order.customer
            auth_user = customer.user

            items_summary = []
            stylist_name = None

            for item in order.order_item:
                if item.service:
                    items_summary.append(item.service.name)

                    # --- Safe stylist lookup via booking/appointment ---
                    booking_obj = None
                    if item.booking:
                        if isinstance(item.booking, (list, tuple)):
                            booking_obj = item.booking[0] if item.booking else None
                        else:
                            booking_obj = item.booking

                    if (
                        booking_obj
                        and booking_obj.appointment
                        and booking_obj.appointment.employee
                    ):
                        emp = booking_obj.appointment.employee
                        stylist_name = f"{emp.first_name} {emp.last_name}"

                elif item.product:
                    items_summary.append(item.product.name)

            # ----- Amount calculation -----
            # Prefer total_amnt, then subtotal, otherwise sum line_total
            total_amount = getattr(order, "total_amnt", None)
            if total_amount is None:
                subtotal = getattr(order, "subtotal", None)
                if subtotal is not None:
                    total_amount = subtotal
                else:
                    total_amount = sum(
                        (item.line_total or 0) for item in order.order_item
                    )

            # ----- Date selection -----
            submitted_at = getattr(order, "submitted_at", None)
            created_at = getattr(order, "created_at", None)
            date_value = submitted_at or created_at

            # ----- Status -----
            # We treat any order with items as effectively "Paid",
            # but still surface the order.status if set.
            raw_status = order.status or "paid"
            status = raw_status.capitalize()

            transactions_list.append({
                # No Payment table: use ORDER-based identifiers
                "transaction_id": f"ORDER-{order.id}",
                "payment_id": None,
                "order_id": order.id,
                "date": date_value.isoformat() if date_value else None,
                "customer_name": f"{customer.first_name} {customer.last_name}",
                "customer_email": auth_user.email,
                "items": items_summary,
                "stylist": stylist_name or "N/A",
                "amount": float(total_amount),
                "payment_method": "N/A",   # No payment record available
                "status": status,
                "refund_reason": getattr(order, "refund_reason", None),
            })

        return jsonify({
            "status": "success",
            "salon_id": salon_id,
            "transaction_count": len(transactions_list),
            "transactions": transactions_list,
        }), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({
            "status": "error",
            "message": "Internal server error",
            "details": str(e),
        }), 500
