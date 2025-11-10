from flask import Blueprint, jsonify, request
from app.extensions import db
from sqlalchemy import func
from datetime import datetime, timedelta

admin_salon_activity_bp = Blueprint("admin_salon_activity_bp", __name__, url_prefix="/api/admin/salons")


# Temporary lightweight ORM references (no changes to models.py) 
class Salon(db.Model):
    __tablename__ = "salon"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255))
    verified = db.Column(db.Boolean, default=False)
    rating = db.Column(db.Float, default=0.0)
    city = db.Column(db.String(100))


class Appointment(db.Model):
    __tablename__ = "appointment"
    id = db.Column(db.Integer, primary_key=True)
    salon_id = db.Column(db.Integer, db.ForeignKey("salon.id"))
    start_time = db.Column(db.DateTime)
    end_time = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

@admin_salon_activity_bp.route("/pending", methods=["GET"])
def get_pending_verifications():
    pending = (
        db.session.query(Salon.id, Salon.name, Salon.verified)
        .filter(Salon.verified == False)
        .all()
    )
    response = [{"id": s.id, "name": s.name, "verified": s.verified} for s in pending]
    return jsonify(response)



