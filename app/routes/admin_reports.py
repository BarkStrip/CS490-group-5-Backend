# app/routes/admin_reports.py
from flask import Blueprint, jsonify, request, send_file
from app.extensions import db
from sqlalchemy import func
from io import BytesIO
import pandas as pd
from datetime import datetime
from app.models import Customers, Appointment, Review, Invoice, Salon

admin_reports_bp = Blueprint("admin_reports_bp", __name__, url_prefix="/api/admin/reports")

@admin_reports_bp.route("/demographics", methods=["GET"])
def get_demographics():
    """Returns gender and age group distribution of users."""
    total_customers = db.session.query(func.count(Customers.id)).scalar() or 0

    # Gender breakdown
    gender_stats = (
        db.session.query(Customers.gender, func.count(Customers.id))
        .group_by(Customers.gender)
        .all()
    )
    gender_data = [{"name": g or "Unknown", "value": c} for g, c in gender_stats]

    # Age groups: 18–24, 25–34, 35–44, 45+
    age_groups = [
        {"age": "18–24", "count": db.session.query(func.count(Customers.id)).filter(Customers.age.between(18, 24)).scalar() or 0},
        {"age": "25–34", "count": db.session.query(func.count(Customers.id)).filter(Customers.age.between(25, 34)).scalar() or 0},
        {"age": "35–44", "count": db.session.query(func.count(Customers.id)).filter(Customers.age.between(35, 44)).scalar() or 0},
        {"age": "45+", "count": db.session.query(func.count(Customers.id)).filter(Customers.age >= 45).scalar() or 0},
    ]

    return jsonify({
        "total_customers": total_customers,
        "gender_distribution": gender_data,
        "age_groups": age_groups
    })

@admin_reports_bp.route("/engagement", methods=["GET"])
def get_engagement():
    """Summarizes user engagement via appointments and reviews."""
    total_appointments = db.session.query(func.count(Appointment.id)).scalar() or 0
    completed_appointments = db.session.query(func.count(Appointment.id)).filter(Appointment.status == "Completed").scalar() or 0
    avg_rating = db.session.query(func.avg(Review.rating)).scalar() or 0.0
    total_reviews = db.session.query(func.count(Review.id)).scalar() or 0

    engagement_rate = round((completed_appointments / total_appointments * 100), 2) if total_appointments else 0.0

    return jsonify({
        "totalAppointments": total_appointments,
        "completedAppointments": completed_appointments,
        "averageRating": round(avg_rating, 2),
        "totalReviews": total_reviews,
        "engagementRate": engagement_rate
    })

@admin_reports_bp.route("/revenue", methods=["GET"])
def get_revenue():
    """Summarizes revenue across invoices."""
    total_revenue = db.session.query(func.sum(Invoice.total)).scalar() or 0.0
    avg_revenue = db.session.query(func.avg(Invoice.total)).scalar() or 0.0

    top_salon_revenue = (
        db.session.query(Salon.name, func.sum(Invoice.total).label("total"))
        .join(Appointment, Appointment.salon_id == Salon.id)
        .group_by(Salon.name)
        .order_by(func.sum(Invoice.total).desc())
        .limit(5)
        .all()
    )

    salon_data = [{"name": name, "total": float(total)} for name, total in top_salon_revenue]

    return jsonify({
        "totalRevenue": round(total_revenue, 2),
        "averageRevenue": round(avg_revenue, 2),
        "topSalons": salon_data
    })



