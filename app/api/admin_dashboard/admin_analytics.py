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


