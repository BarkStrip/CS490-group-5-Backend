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


# ---------------------------------------------------------
# 2. TOP SALONS (by appointment count)
# ---------------------------------------------------------
@admin_salon_activity_bp.route("/top", methods=["GET"])
def get_top_salons():
    rows = (
        db.session.query(
            Salon.name.label("name"),
            func.count(Appointment.id).label("count"),
        )
        .join(Appointment, Appointment.salon_id == Salon.id)
        .group_by(Salon.id)
        .order_by(func.count(Appointment.id).desc())
        .limit(5)
        .all()
    )

    data = [{"name": r.name, "count": int(r.count)} for r in rows]

    return jsonify({"top_salons": data}), 200


# ---------------------------------------------------------
# 3. APPOINTMENT TRENDS (last 7 days)
# ---------------------------------------------------------
@admin_salon_activity_bp.route("/trends", methods=["GET"])
def get_appointment_trends():
    today = datetime.utcnow().date()
    last_7 = today - timedelta(days=6)

    rows = (
        db.session.query(
            func.date(Appointment.created_at).label("day"),
            func.count(Appointment.id).label("count"),
        )
        .filter(func.date(Appointment.created_at) >= last_7)
        .group_by(func.date(Appointment.created_at))
        .order_by(func.date(Appointment.created_at))
        .all()
    )

    data = [{"day": r.day.strftime("%Y-%m-%d"), "count": int(r.count)} for r in rows]

    return jsonify({"trends": data}), 200


@admin_salon_activity_bp.route("/metrics", methods=["GET"])
def get_appointment_metrics():
    """
    Calculate average appointment duration (in minutes)
    using only valid completed appointments.
    """

    MINUTES_LIMIT = 300  # ignore anything above 5 hours

    rows = (
        db.session.query(Appointment.start_at, Appointment.end_at, Appointment.status)
        .filter(Appointment.start_at.isnot(None))
        .filter(Appointment.end_at.isnot(None))
        .filter(Appointment.status == "COMPLETED")
        .all()
    )

    durations = []

    for r in rows:
        if r.start_at and r.end_at:
            diff = (r.end_at - r.start_at).total_seconds() / 60  # minutes
            if 0 < diff <= MINUTES_LIMIT:  # clean data only
                durations.append(diff)

    avg_minutes = round(sum(durations) / len(durations), 1) if durations else 0

    return jsonify({"avg_time": avg_minutes}), 200


@admin_salon_activity_bp.route("/customers-trend", methods=["GET"])
def customers_trend():
    from app.models import Customers

    seven_days = datetime.now() - timedelta(days=7)

    rows = (
        db.session.query(
            func.date(Customers.created_at).label("day"),
            func.count(Customers.id).label("count"),
        )
        .filter(Customers.created_at >= seven_days)
        .group_by(func.date(Customers.created_at))
        .order_by(func.date(Customers.created_at))
        .all()
    )

    data = [{"day": str(r.day), "count": int(r.count)} for r in rows]
    return jsonify({"customers": data})


@admin_salon_activity_bp.route("/salons-trend", methods=["GET"])
def salons_trend():
    from app.models import Salon

    # Last 3 months (90 days)
    ninety_days = datetime.now() - timedelta(days=90)

    rows = (
        db.session.query(
            func.date(Salon.created_at).label("day"),
            func.count(Salon.id).label("count"),
        )
        .filter(Salon.created_at >= ninety_days)
        .group_by(func.date(Salon.created_at))
        .order_by(func.date(Salon.created_at))
        .all()
    )

    data = [{"day": str(r.day), "count": int(r.count)} for r in rows]

    return jsonify({"salons": data})
