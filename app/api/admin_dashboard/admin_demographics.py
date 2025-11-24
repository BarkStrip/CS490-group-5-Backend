# app/routes/admin_demographics.py

from flask import Blueprint, jsonify
from app.extensions import db
from sqlalchemy import func, case
from app.models import Appointment, Salon, Customers, LoyaltyAccount

admin_demographics_bp = Blueprint(
    "admin_demographics_bp",
    __name__,
    url_prefix="/api/admin/demographics",
)


# ---------------------------------------------------------
# 1) APPOINTMENTS BY CITY
# ---------------------------------------------------------
@admin_demographics_bp.route("/appointments-by-city", methods=["GET"])
def appointments_by_city():
    rows = (
        db.session.query(
            Salon.city,
            func.count(Appointment.id)
        )
        .join(Salon, Appointment.salon_id == Salon.id)
        .group_by(Salon.city)
        .all()
    )

    return jsonify([
        {"name": city or "Unknown", "value": int(count)}
        for city, count in rows
    ])


