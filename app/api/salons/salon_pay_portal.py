# app/api/salons/salon_pay_portal.py

from flask import Blueprint, jsonify
from app.extensions import db
from app.models import Employees, Appointment, Salon, Order, OrderItem, Product
from sqlalchemy import and_
from datetime import datetime, timedelta
from decimal import Decimal

# URL prefix will be: /api/salon_payroll/...
salon_payroll_bp = Blueprint("salon_payroll", __name__, url_prefix="/api/salon_payroll")

# Same commission split as employee portal
# Employees get 70% of **service** revenue, salon gets 30% of **service** revenue.
# Products are assumed to be 100% salon revenue (no employee commission).
EMPLOYEE_COMMISSION_RATE = Decimal("0.70")
SALON_SERVICE_SHARE_RATE = Decimal("1.00") - EMPLOYEE_COMMISSION_RATE


def get_biweekly_period(target_date=None):
    """
    Same logic as in employee_pay_portal.get_biweekly_period
    Biweekly periods start on Sunday and run for 14 days.
    """
    if target_date is None:
        target_date = datetime.now().date()

    # Monday=0 -> Sunday=6, so we convert to "days since Sunday"
    days_since_sunday = target_date.weekday() + 1
    if days_since_sunday == 7:  # if today is Sunday
        days_since_sunday = 0

    current_sunday = target_date - timedelta(days=days_since_sunday)

    # Reference Sunday to decide odd/even biweekly cycle
    reference_sunday = datetime(2024, 1, 7).date()
    days_diff = (current_sunday - reference_sunday).days
    weeks_since_reference = days_diff // 7

    # Odd week: go back one week to get the start of the 2-week period
    if weeks_since_reference % 2 == 1:
        period_start = current_sunday - timedelta(days=7)
    else:
        period_start = current_sunday

    period_end = period_start + timedelta(days=13)  # 14 days total

    return period_start, period_end


def get_product_revenue_for_range(salon_id, start_dt, end_dt) -> Decimal:
    """
    Sum product revenue (not services) for a salon in a given datetime range,
    based on OrderItem + Order + Product.

    Uses:
      - OrderItem.line_total if present
      - otherwise unit_price * qty
    Filters:
      - Product.salon_id == salon_id   <-- key change
      - Order.created_at within [start_dt, end_dt]
      - OrderItem.product_id is not NULL
    """
    product_items = (
        db.session.query(OrderItem)
        .join(OrderItem.order)
        .join(OrderItem.product)
        .filter(
            Product.salon_id == salon_id,
            Order.created_at >= start_dt,
            Order.created_at <= end_dt,
            OrderItem.product_id.isnot(None),
        )
        .all()
    )

    total_product_revenue = Decimal("0.00")

    for item in product_items:
        if item.line_total is not None:
            line_total = Decimal(str(item.line_total))
        elif item.unit_price is not None:
            qty = item.qty or 1
            line_total = Decimal(str(item.unit_price)) * Decimal(str(qty))
        else:
            line_total = Decimal("0")

        total_product_revenue += line_total

    return total_product_revenue.quantize(Decimal("0.01"))


@salon_payroll_bp.route("/<int:salon_id>/current-period", methods=["GET"])
def get_current_period_salon(salon_id):
    """
    GET /api/salon_payroll/<salon_id>/current-period
    Aggregated biweekly stats for the entire salon.

    Now includes:
      - service revenue
      - product revenue
      - combined revenue
      - employee earnings (from services only)
      - salon earnings from services + products
    """
    salon = db.session.get(Salon, salon_id)
    if not salon:
        return jsonify({"error": "Salon not found"}), 404

    period_start, period_end = get_biweekly_period()
    period_start_dt = datetime.combine(period_start, datetime.min.time())
    period_end_dt = datetime.combine(period_end, datetime.max.time())

    # Join Appointment -> Employees so we can filter by Employees.salon_id
    # Include COMPLETED + upcoming Booked appointments
    completed_appointments = (
        db.session.query(Appointment)
        .join(Appointment.employee)
        .filter(
            and_(
                Employees.salon_id == salon_id,
                Appointment.status.in_(["COMPLETED", "Booked"]),
                Appointment.start_at >= period_start_dt,
                Appointment.end_at <= period_end_dt,
            )
        )
        .all()
    )

    total_hours = Decimal("0.00")
    total_service_revenue = Decimal("0.00")
    appointment_count = 0

    for apt in completed_appointments:
        if apt.start_at and apt.end_at:
            duration = apt.end_at - apt.start_at
            hours = Decimal(str(duration.total_seconds() / 3600))
            total_hours += hours

            if apt.price_at_book:
                price = Decimal(str(apt.price_at_book))
            else:
                price = Decimal("0")

            total_service_revenue += price
            appointment_count += 1

    total_hours = total_hours.quantize(Decimal("0.01"))
    total_service_revenue = total_service_revenue.quantize(Decimal("0.01"))

    # Product revenue for same biweekly window (based on order timestamps)
    total_product_revenue = get_product_revenue_for_range(
        salon_id, period_start_dt, period_end_dt
    )

    # Combined revenue
    total_revenue = (total_service_revenue + total_product_revenue).quantize(
        Decimal("0.01")
    )

    # Commission logic: employees get 70% of service revenue only
    employee_earnings = (total_service_revenue * EMPLOYEE_COMMISSION_RATE).quantize(
        Decimal("0.01")
    )
    salon_share_services = (total_service_revenue * SALON_SERVICE_SHARE_RATE).quantize(
        Decimal("0.01")
    )

    # Products assumed to be 100% salon revenue
    salon_share_products = total_product_revenue

    # Total salon earnings = 30% of service revenue + 100% of product revenue
    salon_total_earnings = (salon_share_services + salon_share_products).quantize(
        Decimal("0.01")
    )

    result = {
        "salon_id": salon.id,
        "salon_name": salon.name,
        "commission_rate": float(EMPLOYEE_COMMISSION_RATE),
        "commission_percentage": "70% (services) / 30% (services)",
        "hours_worked": float(total_hours),
        "appointments_completed": appointment_count,
        # Service vs product vs total
        "total_service_revenue": float(total_service_revenue),
        "total_product_revenue": float(total_product_revenue),
        "total_revenue": float(total_revenue),
        # Earnings breakdown
        "employee_earnings": float(employee_earnings),  # employees (services only)
        "salon_share_services": float(
            salon_share_services
        ),  # salon from services (30%)
        "salon_share_products": float(
            salon_share_products
        ),  # salon from products (100%)
        "salon_share": float(salon_share_services),  # kept for clarity / legacy
        "salon_total_earnings": float(salon_total_earnings),  # services + products
        "pay_period": {
            "start_date": period_start.isoformat(),
            "end_date": period_end.isoformat(),
            "period_label": f"{period_start.strftime('%b %d')} - {period_end.strftime('%b %d, %Y')}",
        },
    }

    return jsonify(result), 200


@salon_payroll_bp.route("/<int:salon_id>/history", methods=["GET"])
def get_salon_payroll_history(salon_id):
    """
    GET /api/salon_payroll/<salon_id>/history
    Last 6 biweekly periods, aggregated across all employees.

    Now includes service revenue, product revenue, total revenue,
    and salon_total_earnings for each period.
    """
    salon = db.session.get(Salon, salon_id)
    if not salon:
        return jsonify({"error": "Salon not found"}), 404

    history = []

    for i in range(6):
        target_date = datetime.now().date() - timedelta(weeks=i * 2)
        period_start, period_end = get_biweekly_period(target_date)

        period_start_dt = datetime.combine(period_start, datetime.min.time())
        period_end_dt = datetime.combine(period_end, datetime.max.time())

        completed_appointments = (
            db.session.query(Appointment)
            .join(Appointment.employee)
            .filter(
                and_(
                    Employees.salon_id == salon_id,
                    Appointment.status.in_(["COMPLETED", "Booked"]),
                    Appointment.start_at >= period_start_dt,
                    Appointment.end_at <= period_end_dt,
                )
            )
            .all()
        )

        total_hours = Decimal("0.00")
        total_service_revenue = Decimal("0.00")
        appointment_count = 0

        for apt in completed_appointments:
            if apt.start_at and apt.end_at:
                duration = apt.end_at - apt.start_at
                hours = Decimal(str(duration.total_seconds() / 3600))
                total_hours += hours

                if apt.price_at_book:
                    price = Decimal(str(apt.price_at_book))
                else:
                    price = Decimal("0")

                total_service_revenue += price
                appointment_count += 1

        total_hours = total_hours.quantize(Decimal("0.01"))
        total_service_revenue = total_service_revenue.quantize(Decimal("0.01"))

        total_product_revenue = get_product_revenue_for_range(
            salon_id, period_start_dt, period_end_dt
        )

        total_revenue = (total_service_revenue + total_product_revenue).quantize(
            Decimal("0.01")
        )

        salon_share_services = (
            total_service_revenue * SALON_SERVICE_SHARE_RATE
        ).quantize(Decimal("0.01"))
        salon_share_products = total_product_revenue
        salon_total_earnings = (salon_share_services + salon_share_products).quantize(
            Decimal("0.01")
        )

        history.append(
            {
                "period_start": period_start.isoformat(),
                "period_end": period_end.isoformat(),
                "period_label": f"{period_start.strftime('%b %d')} - {period_end.strftime('%b %d, %Y')}",
                "hours_worked": float(total_hours),
                "appointments_completed": appointment_count,
                "total_service_revenue": float(total_service_revenue),
                "total_product_revenue": float(total_product_revenue),
                "total_revenue": float(total_revenue),
                "salon_share_services": float(salon_share_services),
                "salon_share_products": float(salon_share_products),
                "salon_share": float(salon_share_services),
                "salon_total_earnings": float(salon_total_earnings),
            }
        )

    return (
        jsonify(
            {
                "salon_id": salon.id,
                "salon_name": salon.name,
                "commission_rate": float(EMPLOYEE_COMMISSION_RATE),
                "commission_percentage": "70% (services) / 30% (services)",
                "history": history,
            }
        ),
        200,
    )


@salon_payroll_bp.route("/<int:salon_id>/monthly-total", methods=["GET"])
def get_salon_monthly_total(salon_id):
    """
    GET /api/salon_payroll/<salon_id>/monthly-total
    Monthly totals for the entire salon.

    Includes:
      - service revenue
      - product revenue
      - total revenue
      - employee earnings (services)
      - salon earnings (services + products)
    """
    salon = db.session.get(Salon, salon_id)
    if not salon:
        return jsonify({"error": "Salon not found"}), 404

    now = datetime.now()
    month_start = datetime(now.year, now.month, 1)

    if now.month == 12:
        month_end = datetime(now.year + 1, 1, 1) - timedelta(seconds=1)
    else:
        month_end = datetime(now.year, now.month + 1, 1) - timedelta(seconds=1)

    completed_appointments = (
        db.session.query(Appointment)
        .join(Appointment.employee)
        .filter(
            and_(
                Employees.salon_id == salon_id,
                Appointment.status.in_(["COMPLETED", "Booked"]),
                Appointment.start_at >= month_start,
                Appointment.end_at <= month_end,
            )
        )
        .all()
    )

    total_hours = Decimal("0.00")
    total_service_revenue = Decimal("0.00")
    appointment_count = 0

    for apt in completed_appointments:
        if apt.start_at and apt.end_at:
            duration = apt.end_at - apt.start_at
            hours = Decimal(str(duration.total_seconds() / 3600))
            total_hours += hours

            if apt.price_at_book:
                price = Decimal(str(apt.price_at_book))
            else:
                price = Decimal("0")

            total_service_revenue += price
            appointment_count += 1

    total_hours = total_hours.quantize(Decimal("0.01"))
    total_service_revenue = total_service_revenue.quantize(Decimal("0.01"))

    # Product revenue for this month
    total_product_revenue = get_product_revenue_for_range(
        salon_id, month_start, month_end
    )

    total_revenue = (total_service_revenue + total_product_revenue).quantize(
        Decimal("0.01")
    )

    employee_earnings = (total_service_revenue * EMPLOYEE_COMMISSION_RATE).quantize(
        Decimal("0.01")
    )
    salon_share_services = (total_service_revenue * SALON_SERVICE_SHARE_RATE).quantize(
        Decimal("0.01")
    )
    salon_share_products = total_product_revenue
    salon_total_earnings = (salon_share_services + salon_share_products).quantize(
        Decimal("0.01")
    )

    return (
        jsonify(
            {
                "salon_id": salon.id,
                "salon_name": salon.name,
                "month": now.strftime("%B %Y"),
                "month_start": month_start.date().isoformat(),
                "month_end": month_end.date().isoformat(),
                "hours_worked": float(total_hours),
                "appointments_completed": appointment_count,
                "total_service_revenue": float(total_service_revenue),
                "total_product_revenue": float(total_product_revenue),
                "total_revenue": float(total_revenue),
                "employee_earnings": float(employee_earnings),
                "salon_share_services": float(salon_share_services),
                "salon_share_products": float(salon_share_products),
                "salon_share": float(salon_share_services),
                "salon_total_earnings": float(salon_total_earnings),
                "commission_percentage": "70% (services) / 30% (services)",
            }
        ),
        200,
    )
