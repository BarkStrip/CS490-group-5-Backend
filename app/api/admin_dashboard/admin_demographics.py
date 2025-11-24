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

# ---------------------------------------------------------
# 2) LOYALTY SEGMENTS (Loyalty vs Guests)
# ---------------------------------------------------------
@admin_demographics_bp.route("/loyalty-segments", methods=["GET"])
def loyalty_segments():

    total_users = db.session.query(func.count(Customers.id)).scalar() or 0

    loyalty_users = (
        db.session.query(func.count(func.distinct(LoyaltyAccount.user_id)))
        .scalar()
        or 0
    )

    guest_users = total_users - loyalty_users

    return jsonify([
        {"segment": "Loyalty Members", "count": int(loyalty_users)},
        {"segment": "Guests", "count": int(guest_users)},
    ])


