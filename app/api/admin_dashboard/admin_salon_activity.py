from flask import Blueprint, jsonify
from datetime import datetime, timedelta
from sqlalchemy import func
from app.extensions import db
from app.models import Appointment, Salon, SalonVerify

admin_salon_activity_bp = Blueprint(
    "admin_salon_activity_bp", __name__, url_prefix="/api/admin/salon-activity"
)

# ---------------------------------------------------------
# 1. PENDING SALON VERIFICATIONS
# ---------------------------------------------------------
@admin_salon_activity_bp.route("/pending", methods=["GET"])
def get_pending_verifications():
    rows = (
        db.session.query(
            SalonVerify.id.label("verification_id"),
            Salon.id.label("salon_id"),
            Salon.name.label("name"),
        )
        .join(Salon, SalonVerify.salon_id == Salon.id)
        .filter(SalonVerify.status == "PENDING")
        .all()
    )

    data = [
        {
            "verification_id": r.verification_id,
            "salon_id": r.salon_id,
            "name": r.name,
        }
        for r in rows
    ]

    return jsonify({"pending": data}), 200


