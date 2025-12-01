from flask import Blueprint, jsonify
from datetime import datetime, timedelta
from app.extensions import db
from sqlalchemy import func
from app.models import Customers, Salon, Appointment

admin_analytics_bp = Blueprint(
    "admin_analytics_bp",
    __name__,
    url_prefix="/api/admin/analytics",
)


# -------------------------------------------------------------------
# 1) SUMMARY: Active users, salons, appointments, retention rate
# -------------------------------------------------------------------
@admin_analytics_bp.route("/summary", methods=["GET"])
def get_summary():
    """High-level engagement summary for the admin dashboard."""

    active_users = db.session.query(func.count(Customers.id)).scalar() or 0
    total_salons = db.session.query(func.count(Salon.id)).scalar() or 0
    total_appointments = db.session.query(func.count(Appointment.id)).scalar() or 0

    # Simple retention proxy: (appointments / users) * 10
    retention_rate = 0.0
    if active_users > 0:
        retention_rate = round((total_appointments / active_users) * 10, 2)

    return jsonify(
        {
            "activeUsers": active_users,
            "totalSalons": total_salons,
            "totalAppointments": total_appointments,
            "retentionRate": retention_rate,
        }
    )


# -------------------------------------------------------------------
# 2) ENGAGEMENT TREND: appointments per day (last 7 days)--> not used
# -------------------------------------------------------------------
@admin_analytics_bp.route("/engagement-trend", methods=["GET"])
def get_engagement_trend():
    """Number of appointments created per day over the past 7 days."""

    seven_days_ago = datetime.now() - timedelta(days=7)

    rows = (
        db.session.query(
            func.date(Appointment.created_at).label("day"),
            func.count(Appointment.id).label("users"),
        )
        .filter(Appointment.created_at >= seven_days_ago)
        .group_by(func.date(Appointment.created_at))
        .order_by(func.date(Appointment.created_at))
        .all()
    )

    data = [{"day": str(r.day), "users": int(r.users)} for r in rows]
    return jsonify(data)


# -------------------------------------------------------------------
# 3) FEATURE USAGE: group salons by type (or fallback "Unknown")--> not used
# -------------------------------------------------------------------
@admin_analytics_bp.route("/feature-usage", methods=["GET"])
def get_feature_usage():
    """
    Approximates 'feature usage' by counting salons per type/category.
    Uses Salon.type if present in your schema; falls back to 'Unknown'.
    """

    rows = (
        db.session.query(
            Salon.type.label("name"),
            func.count(Salon.id).label("value"),
        )
        .group_by(Salon.type)
        .all()
    )

    data = [{"name": (r.name or "Unknown"), "value": int(r.value)} for r in rows]
    return jsonify(data)


# -------------------------------------------------------------------
# 4) RETENTION COHORT: appointments grouped by month
# -------------------------------------------------------------------
@admin_analytics_bp.route("/retention-cohort", methods=["GET"])
def get_retention_cohort():
    """
    Cohort-style view: total appointments per month.
    Uses MySQL DATE_FORMAT via func.date_format.
    """

    rows = (
        db.session.query(
            func.date_format(Appointment.created_at, "%b").label("month"),
            func.count(Appointment.id).label("rate"),
        )
        .group_by(func.date_format(Appointment.created_at, "%b"))
        .order_by(func.min(Appointment.created_at))
        .all()
    )

    data = [{"month": r.month, "rate": int(r.rate)} for r in rows]
    return jsonify(data)


# -------------------------------------------------------------------
# RETURNING USERS TREND (Last 30 Days)
# -------------------------------------------------------------------
@admin_analytics_bp.route("/returning-users-trend", methods=["GET"])
def get_returning_users_trend():
    """Returning users per day in the last 30 days."""

    days_window = 30
    date_limit = datetime.utcnow() - timedelta(days=days_window)

    # Subquery: customers with more than 1 lifetime appointment
    returning_customers = (
        db.session.query(Appointment.customer_id)
        .group_by(Appointment.customer_id)
        .having(func.count(Appointment.id) > 1)
        .subquery()
    )

    rows = (
        db.session.query(
            func.date(Appointment.created_at).label("day"),
            func.count(Appointment.id).label("returning_users"),
        )
        .filter(Appointment.customer_id.in_(returning_customers))
        .filter(Appointment.created_at >= date_limit)
        .group_by(func.date(Appointment.created_at))
        .order_by(func.date(Appointment.created_at))
        .all()
    )

    data = [
        {"day": r.day.strftime("%Y-%m-%d"), "returning_users": int(r.returning_users)}
        for r in rows
    ]

    return jsonify({"trend": data}), 200
