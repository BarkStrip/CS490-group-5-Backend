# app/api/salons/salon_pay_portal.py

from flask import Blueprint, jsonify
from app.extensions import db
from app.models import Employees, Appointment, Salon
from sqlalchemy import and_
from datetime import datetime, timedelta
from decimal import Decimal

# URL prefix will be: /api/salon_payroll/...
salon_payroll_bp = Blueprint("salon_payroll", __name__, url_prefix="/api/salon_payroll")

# Same commission split as employee portal
EMPLOYEE_COMMISSION_RATE = Decimal("0.70")


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


@salon_payroll_bp.route("/<int:salon_id>/current-period", methods=["GET"])
def get_current_period_salon(salon_id):
    """
    GET /api/salon_payroll/<salon_id>/current-period
    Aggregated biweekly stats for the entire salon.
    """
    salon = db.session.get(Salon, salon_id)
    if not salon:
        return jsonify({"error": "Salon not found"}), 404

    period_start, period_end = get_biweekly_period()
    period_start_dt = datetime.combine(period_start, datetime.min.time())
    period_end_dt = datetime.combine(period_end, datetime.max.time())

    # Join Appointment -> Employees so we can filter by Employees.salon_id
    completed_appointments = (
        db.session.query(Appointment)
        .join(Appointment.employee)
        .filter(
            and_(
                Employees.salon_id == salon_id,
                # If you use status, uncomment:
                # Appointment.status == "COMPLETED",
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

    employee_earnings = (total_service_revenue * EMPLOYEE_COMMISSION_RATE).quantize(
        Decimal("0.01")
    )
    salon_share = (
        total_service_revenue * (Decimal("1") - EMPLOYEE_COMMISSION_RATE)
    ).quantize(Decimal("0.01"))

    result = {
        "salon_id": salon.id,
        "salon_name": salon.name,
        "commission_rate": float(EMPLOYEE_COMMISSION_RATE),
        "commission_percentage": "70% / 30%",
        "hours_worked": float(total_hours),
        "appointments_completed": appointment_count,
        "total_service_revenue": float(total_service_revenue),
        "employee_earnings": float(employee_earnings),  # total paid to staff
        "salon_share": float(salon_share),  # what the salon keeps
        "projected_paycheck": float(salon_share),  # for UI consistency
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
                    # Appointment.status == "COMPLETED",
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
        salon_share = (
            total_service_revenue * (Decimal("1") - EMPLOYEE_COMMISSION_RATE)
        ).quantize(Decimal("0.01"))

        history.append(
            {
                "period_start": period_start.isoformat(),
                "period_end": period_end.isoformat(),
                "period_label": f"{period_start.strftime('%b %d')} - {period_end.strftime('%b %d, %Y')}",
                "hours_worked": float(total_hours),
                "appointments_completed": appointment_count,
                "total_service_revenue": float(total_service_revenue),
                "salon_share": float(salon_share),
            }
        )

    return (
        jsonify(
            {
                "salon_id": salon.id,
                "salon_name": salon.name,
                "commission_rate": float(EMPLOYEE_COMMISSION_RATE),
                "commission_percentage": "70% / 30%",
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
                # Appointment.status == "COMPLETED",
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
    employee_earnings = (total_service_revenue * EMPLOYEE_COMMISSION_RATE).quantize(
        Decimal("0.01")
    )
    salon_share = (
        total_service_revenue * (Decimal("1") - EMPLOYEE_COMMISSION_RATE)
    ).quantize(Decimal("0.01"))

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
                "employee_earnings": float(employee_earnings),
                "salon_share": float(salon_share),
                "commission_percentage": "70% / 30%",
            }
        ),
        200,
    )
