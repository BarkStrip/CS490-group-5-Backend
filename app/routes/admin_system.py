from flask import Blueprint, jsonify
from app.extensions import db
from sqlalchemy import func
from datetime import datetime

admin_system_bp = Blueprint("admin_system_bp", __name__, url_prefix="/api/admin/system")

class SystemLog(db.Model):
    __tablename__ = "system_log"
    id = db.Column(db.Integer, primary_key=True)
    component = db.Column(db.String(50), nullable=False)
    uptime_percent = db.Column(db.Float, nullable=False)
    status_msg = db.Column(db.String(255))
    affected_users = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)


class Salon(db.Model):
    __tablename__ = "salon"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100))
    city = db.Column(db.String(100))

@admin_system_bp.route("/status", methods=["GET"])
def get_status():
    """
    Returns average uptime % and latest status per component.
    """
    components = (
        db.session.query(
            SystemLog.component,
            func.avg(SystemLog.uptime_percent).label("avg_uptime"),
            func.max(SystemLog.status_msg).label("latest_status"),
        )
        .group_by(SystemLog.component)
        .all()
    )

    data = {}
    for component, avg_uptime, latest_status in components:
        key = component.lower().replace(" ", "_")
        data[key] = {
            "status": latest_status or f"{round(avg_uptime, 2)}% Operational",
            "operational": round(avg_uptime, 2),
        }

    # compute platform-wide average
    data["platform_uptime"] = (
        round(sum(avg for _, avg, _ in components) / len(components), 2)
        if components
        else 0.0
    )

    return jsonify(data)


