# Invoices, refunds, tracking
from flask import Blueprint, jsonify
from ...extensions import db
from ...models import Payment, Salon, Order, Customers, OrderItem, Booking, Appointment
from sqlalchemy import select
from sqlalchemy.orm import joinedload, selectinload

# Create a new blueprint for payments
receipts_bp = Blueprint("payment", __name__, url_prefix="/api/receipts")


# -------------------------------------------------------------------------
# GET /api/payment/salon/<int:salon_id>/transactions
# Purpose: Get all transactions for a specific salon, formatted for
#          the SalonOwner Payment page.
# -------------------------------------------------------------------------
@receipts_bp.route("/salon/<int:salon_id>/transactions", methods=["GET"])
def get_salon_transactions(salon_id):
    """
    Returns all transactions for a given salon id, including
    customer info, item details, and payment status.
    """
    try:
        salon = db.session.get(Salon, salon_id)
        if not salon:
            return (
                jsonify(
                    {
                        "status": "error",
                        "message": f"Salon with id {salon_id} not found",
                    }
                ),
                404,
            )

        query = (
            select(Payment)
            .join(Payment.order)
            .where(Order.salon_id == salon_id)
            .options(
                joinedload(Payment.pay_method),
                joinedload(Payment.order).options(
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
                ),
            )
            .order_by(Payment.created_at.desc())
        )

        payments = db.session.scalars(query).all()

        transactions_list = []
        for payment in payments:
            order = payment.order

            if not order or not order.customer or not order.customer.user:
                continue

            customer = order.customer
            auth_user = customer.user

            items_summary = []
            stylist_name = None

            for item in order.order_item:
                if item.service:
                    items_summary.append(item.service.name)

                    if item.booking:
                        if item.booking[0].appointment:
                            appointment = item.booking[0].appointment
                            if appointment.employee:
                                emp = appointment.employee
                                stylist_name = f"{emp.first_name} {emp.last_name}"

                elif item.product:
                    items_summary.append(item.product.name)

            status = ""
            if payment.status == "FAILED":
                status = "Failed"
            elif payment.status == "PENDING":
                status = "Pending"
            elif payment.status == "SUCCESSFUL":

                status = order.status

            transactions_list.append(
                {
                    "transaction_id": payment.transaction_id,
                    "payment_id": payment.id,
                    "order_id": order.id,
                    "date": payment.created_at.isoformat(),
                    "customer_name": f"{customer.first_name} {customer.last_name}",
                    "customer_email": auth_user.email,
                    "items": items_summary,
                    "stylist": stylist_name or "N/A",
                    "amount": float(payment.amount),
                    "payment_method": (
                        payment.pay_method.brand if payment.pay_method else "Unknown"
                    ),
                    "status": status.capitalize() if status else "Unknown",
                    "refund_reason": order.refund_reason,
                }
            )

        return (
            jsonify(
                {
                    "status": "success",
                    "salon_id": salon_id,
                    "transaction_count": len(transactions_list),
                    "transactions": transactions_list,
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
