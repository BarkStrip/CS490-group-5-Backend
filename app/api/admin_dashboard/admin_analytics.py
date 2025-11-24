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
# 2) ENGAGEMENT TREND: appointments per day (last 7 days)
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
# 3) FEATURE USAGE: group salons by type (or fallback "Unknown")
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

    data = [
        {"name": (r.name or "Unknown"), "value": int(r.value)}
        for r in rows
    ]
    return jsonify(data)


