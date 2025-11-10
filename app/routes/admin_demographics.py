from flask import Blueprint, jsonify
from app.extensions import db
from app.models import Customers 
from sqlalchemy import func
from datetime import date

admin_demo_bp = Blueprint("admin_demo_bp", __name__, url_prefix="/api/admin/users")

@admin_demo_bp.route("/gender", methods=["GET"])
def get_gender_distribution():
    data = (
        db.session.query(
            Customers.gender.label("name"),
            func.count(Customers.id).label("value")
        )
        .group_by(Customers.gender)
        .all()
    )
    result = [{"name": r.name or "Unspecified", "value": r.value} for r in data]
    return jsonify(result)


@admin_demo_bp.route("/age-distribution", methods=["GET"])
def get_age_distribution():
    today = date.today()
    age_groups = {
        "18–24": (18, 24),
        "25–34": (25, 34),
        "35–44": (35, 44),
        "45+": (45, 200)
    }

    output = []
    for label, (min_age, max_age) in age_groups.items():
        count = (
            db.session.query(func.count(Customers.id))
            .filter(
                func.timestampdiff(func.YEAR, Customers.date_of_birth, today) >= min_age,
                func.timestampdiff(func.YEAR, Customers.date_of_birth, today) <= max_age
            )
            .scalar()
        )
        output.append({"age": label, "count": count or 0})
    return jsonify(output)
