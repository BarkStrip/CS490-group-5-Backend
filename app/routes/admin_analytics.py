# app/routes/admin_analytics.py
from flask import Blueprint, jsonify
from app.extensions import db
from sqlalchemy import func
from datetime import datetime, timedelta

admin_analytics_bp = Blueprint("admin_analytics_bp", __name__, url_prefix="/api/admin/analytics")

# --- Define models dynamically (if not already imported) ---
# You can skip these if they’re already in models.py and imported elsewhere
class Customer(db.Model):
    __tablename__ = "customers"
    id = db.Column(db.Integer, primary_key=True)
    created_at = db.Column(db.DateTime)

class Salon(db.Model):
    __tablename__ = "salon"
    id = db.Column(db.Integer, primary_key=True)
    type = db.Column(db.String(255))
    created_at = db.Column(db.DateTime)

class Appointment(db.Model):
    __tablename__ = "appointment"
    id = db.Column(db.Integer, primary_key=True)
    created_at = db.Column(db.DateTime)
    salon_id = db.Column(db.Integer, db.ForeignKey("salon.id"))
    customer_id = db.Column(db.Integer, db.ForeignKey("customers.id"))

@admin_analytics_bp.route("/summary", methods=["GET"])
def get_summary():
    active_users = db.session.query(func.count(Customer.id)).scalar() or 0
    total_salons = db.session.query(func.count(Salon.id)).scalar() or 0
    total_appointments = db.session.query(func.count(Appointment.id)).scalar() or 0

    # Retention Rate = (appointments / users) * 10
    retention_rate = round((total_appointments / active_users * 10), 2) if active_users else 0.0

    return jsonify({
        "activeUsers": active_users,
        "totalSalons": total_salons,
        "totalAppointments": total_appointments,
        "retentionRate": retention_rate
    })


