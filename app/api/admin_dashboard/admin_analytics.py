
import io
from datetime import datetime, timedelta

from flask import Blueprint, jsonify, request, send_file
from sqlalchemy import func
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas
from app.extensions import db
from app.models import Customers, Salon, Appointment
from datetime import datetime, timedelta
from sqlalchemy import func



admin_analytics_bp = Blueprint(
    "admin_analytics_bp",
    __name__,
    url_prefix="/api/admin/analytics",
)


# -------------------------------------------------------------------
# Helper: parse date range from query params
# -------------------------------------------------------------------
def _parse_date_range(default_days: int = 30):
    """
    Reads ?from=YYYY-MM-DD & ?to=YYYY-MM-DD from query params.
    If not provided, uses [today - default_days, today].
    Returns (start_datetime, end_datetime).
    end_datetime is exclusive (for `<` comparisons).
    """
    to_str = request.args.get("to")
    from_str = request.args.get("from")
    days = request.args.get("days", type=int) or default_days

    # default: now in UTC
    end_dt = datetime.utcnow()
    if to_str:
        # accept date only
        end_dt = datetime.fromisoformat(to_str)

    if from_str:
        start_dt = datetime.fromisoformat(from_str)
    else:
        start_dt = end_dt - timedelta(days=days)

    # make end exclusive
    end_dt = end_dt + timedelta(days=1)
    return start_dt, end_dt


# -------------------------------------------------------------------
# 0) SIMPLE ALL-TIME SUMMARY  (kept for convenience / other pages)
# -------------------------------------------------------------------
@admin_analytics_bp.route("/summary", methods=["GET"])
def get_summary():
    """
    All-time simple summary:
    - activeUsers: all customers
    - totalSalons: all salons
    - totalAppointments: all appointments
    - retentionRate: simple proxy (appointments / users * 10)
    This is mostly for backwards compatibility; the dashboard should
    prefer /engagement/summary.
    """
    active_users = db.session.query(func.count(Customers.id)).scalar() or 0
    total_salons = db.session.query(func.count(Salon.id)).scalar() or 0
    total_appointments = db.session.query(func.count(Appointment.id)).scalar() or 0

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
    ), 200


# -------------------------------------------------------------------
# 1) ENGAGEMENT SUMMARY (main API for dashboard cards)
# -------------------------------------------------------------------
@admin_analytics_bp.route("/engagement/summary", methods=["GET"])
def get_engagement_summary():
    """
    Engagement stats for a date range:

    - activeUsers: distinct customers with >=1 appointment in range
    - newUsers: customers created in range
    - totalAppointments: appointments in range
    - returningUsers: active users with >1 lifetime appointment
    - retentionRate: returningUsers / activeUsers  (0–1)
    - retentionRatePercent: retentionRate * 100
    - totalSalons: total salons (all-time)

    Query params:
      ?from=YYYY-MM-DD
      ?to=YYYY-MM-DD
      ?days=N         (fallback if from/to not provided, default 30)
      ?salonId=ID     (optional filter)
    """
    start_dt, end_dt = _parse_date_range(default_days=30)
    salon_id = request.args.get("salonId", type=int)

    # NEW: total customers all-time
    total_customers = (
        db.session.query(func.count(Customers.id)).scalar() or 0
    )

    # Base appointment filters for the window
    appt_filters = [
        Appointment.created_at >= start_dt,
        Appointment.created_at < end_dt,
    ]
    if salon_id:
        appt_filters.append(Appointment.salon_id == salon_id)

    # Active users = distinct customers with appt in range
    active_users = (
        db.session.query(func.count(func.distinct(Appointment.customer_id)))
        .filter(*appt_filters)
        .scalar()
        or 0
    )

    # New users = customers created in range
    customer_filters = [
        Customers.created_at >= start_dt,
        Customers.created_at < end_dt,
    ]
    new_users = (
        db.session.query(func.count(Customers.id))
        .filter(*customer_filters)
        .scalar()
        or 0
    )

    # Total appointments in range
    total_appointments = (
        db.session.query(func.count(Appointment.id))
        .filter(*appt_filters)
        .scalar()
        or 0
    )

    # Returning users:
    #   lifetime appt count > 1 AND they had >=1 appt in this window
    lifetime_counts = (
        db.session.query(
            Appointment.customer_id.label("cid"),
            func.count(Appointment.id).label("num_appts"),
        )
        .group_by(Appointment.customer_id)
        .subquery()
    )

    returning_ids_subq = (
        db.session.query(lifetime_counts.c.cid)
        .filter(lifetime_counts.c.num_appts > 1)
        .subquery()
    )

    returning_filters = [
        Appointment.customer_id.in_(returning_ids_subq),
        Appointment.created_at >= start_dt,
        Appointment.created_at < end_dt,
    ]
    if salon_id:
        returning_filters.append(Appointment.salon_id == salon_id)

    returning_users = (
        db.session.query(func.count(func.distinct(Appointment.customer_id)))
        .filter(*returning_filters)
        .scalar()
        or 0
    )

    retention_rate = 0.0
    if active_users > 0:
        retention_rate = round(returning_users / active_users, 3)

    retention_rate_percent = round(retention_rate * 100, 2)

    total_salons = db.session.query(func.count(Salon.id)).scalar() or 0

    return jsonify(
        {
            "start": start_dt.date().isoformat(),
            "end": (end_dt - timedelta(days=1)).date().isoformat(),
            "salonId": salon_id,
            "activeUsers": active_users,
            "newUsers": new_users,
            "totalAppointments": total_appointments,
            "returningUsers": returning_users,
            "retentionRate": retention_rate,
            "retentionRatePercent": retention_rate_percent,
            "totalSalons": total_salons,
            "totalCustomers": total_customers,
        }
    ), 200


# -------------------------------------------------------------------
# 2) ENGAGEMENT TREND: appointments per day in range
# -------------------------------------------------------------------
@admin_analytics_bp.route("/engagement-trend", methods=["GET"])
def get_engagement_trend():
    """
    Appointments per day over the selected window.

    Params:
      ?from, ?to, ?days (like engagement/summary)
      ?salonId=ID
    """
    start_dt, end_dt = _parse_date_range(default_days=30)
    salon_id = request.args.get("salonId", type=int)

    filters = [
        Appointment.created_at >= start_dt,
        Appointment.created_at < end_dt,
    ]
    if salon_id:
        filters.append(Appointment.salon_id == salon_id)

    rows = (
        db.session.query(
            func.date(Appointment.created_at).label("day"),
            func.count(Appointment.id).label("count"),
        )
        .filter(*filters)
        .group_by(func.date(Appointment.created_at))
        .order_by(func.date(Appointment.created_at))
        .all()
    )

    data = [{"day": r.day.strftime("%Y-%m-%d"), "count": int(r.count)} for r in rows]
    return jsonify({"trend": data}), 200


# -------------------------------------------------------------------
# 3) RETURNING USERS TREND (Last N days, default 30)
# -------------------------------------------------------------------
@admin_analytics_bp.route("/returning-users-trend", methods=["GET"])
def get_returning_users_trend():
    """
    Returning users per day in a window.

    Params:
      ?from, ?to, ?days (default 30)
      ?salonId=ID
    """
    start_dt, end_dt = _parse_date_range(default_days=30)
    salon_id = request.args.get("salonId", type=int)

    # Customers with more than 1 lifetime appointment
    returning_customers = (
        db.session.query(Appointment.customer_id)
        .group_by(Appointment.customer_id)
        .having(func.count(Appointment.id) > 1)
        .subquery()
    )

    filters = [
        Appointment.customer_id.in_(returning_customers),
        Appointment.created_at >= start_dt,
        Appointment.created_at < end_dt,
    ]
    if salon_id:
        filters.append(Appointment.salon_id == salon_id)

    rows = (
        db.session.query(
            func.date(Appointment.created_at).label("day"),
            func.count(Appointment.id).label("returning_users"),
        )
        .filter(*filters)
        .group_by(func.date(Appointment.created_at))
        .order_by(func.date(Appointment.created_at))
        .all()
    )

    data = [
        {"day": r.day.strftime("%Y-%m-%d"), "returning_users": int(r.returning_users)}
        for r in rows
    ]

    return jsonify({"trend": data}), 200


# -------------------------------------------------------------------
# 4) RETENTION COHORT: appointments grouped by month (for bar chart)
# -------------------------------------------------------------------
@admin_analytics_bp.route("/retention-cohort", methods=["GET"])
def get_retention_cohort():
    """
    Cohort-style view: total appointments per calendar month.
    Uses MySQL DATE_FORMAT via func.date_format.
    """

    rows = (
        db.session.query(
            func.date_format(Appointment.created_at, "%b").label("month"),
            func.count(Appointment.id).label("rate"),
        )
        .group_by(func.date_format(Appointment.created_at, "%b"))
        .order_by(func.min(Appointment.created_at))
        .all()
    )

    data = [{"month": r.month, "rate": int(r.rate)} for r in rows]
    return jsonify(data), 200


# -------------------------------------------------------------------
# 5) ENGAGEMENT REPORT PDF – same window as dashboard
# -------------------------------------------------------------------
@admin_analytics_bp.route("/engagement/report-pdf", methods=["GET"])
def generate_engagement_pdf():
    """
    Generate a PDF report matching the dashboard:
      - Summary
      - Appointments (daily)
      - Returning users (daily)
      - Cohort retention (monthly)
    """
    start_dt, end_dt = _parse_date_range(default_days=30)
    salon_id = request.args.get("salonId", type=int)

    # -----------------------------
    # SUMMARY VALUES
    # -----------------------------
    total_customers = db.session.query(func.count(Customers.id)).scalar() or 0

    appt_filters = [
        Appointment.created_at >= start_dt,
        Appointment.created_at < end_dt,
    ]
    if salon_id:
        appt_filters.append(Appointment.salon_id == salon_id)

    active_users = (
        db.session.query(func.count(func.distinct(Appointment.customer_id)))
        .filter(*appt_filters)
        .scalar()
        or 0
    )

    new_users = (
        db.session.query(func.count(Customers.id))
        .filter(Customers.created_at >= start_dt,
                Customers.created_at < end_dt)
        .scalar()
        or 0
    )

    total_appointments = (
        db.session.query(func.count(Appointment.id))
        .filter(*appt_filters)
        .scalar()
        or 0
    )

    # Returning users (lifetime >1 + active in range)
    lifetime_counts = (
        db.session.query(
            Appointment.customer_id,
            func.count(Appointment.id).label("num"),
        )
        .group_by(Appointment.customer_id)
        .subquery()
    )

    returning_ids = (
        db.session.query(lifetime_counts.c.customer_id)
        .filter(lifetime_counts.c.num > 1)
        .subquery()
    )

    returning_filters = [
        Appointment.customer_id.in_(returning_ids),
        Appointment.created_at >= start_dt,
        Appointment.created_at < end_dt,
    ]
    if salon_id:
        returning_filters.append(Appointment.salon_id == salon_id)

    returning_users = (
        db.session.query(func.count(func.distinct(Appointment.customer_id)))
        .filter(*returning_filters)
        .scalar()
        or 0
    )

    retention_rate = (returning_users / active_users * 100) if active_users else 0

    total_salons = db.session.query(func.count(Salon.id)).scalar() or 0

    # -----------------------------
    # TREND: Appointments per Day
    # -----------------------------
    appt_trend = (
        db.session.query(
            func.date(Appointment.created_at).label("day"),
            func.count(Appointment.id).label("count"),
        )
        .filter(*appt_filters)
        .group_by(func.date(Appointment.created_at))
        .order_by(func.date(Appointment.created_at))
        .all()
    )

    # -----------------------------
    # TREND: Returning Users per Day
    # -----------------------------
    returning_trend = (
        db.session.query(
            func.date(Appointment.created_at).label("day"),
            func.count(Appointment.id).label("returning"),
        )
        .filter(*returning_filters)
        .group_by(func.date(Appointment.created_at))
        .order_by(func.date(Appointment.created_at))
        .all()
    )

    # -----------------------------
    # COHORT RETENTION (MONTHLY)
    # -----------------------------
    cohort_rows = (
        db.session.query(
            func.date_format(Appointment.created_at, "%b").label("month"),
            func.count(Appointment.id).label("count"),
        )
        .group_by(func.date_format(Appointment.created_at, "%b"))
        .order_by(func.min(Appointment.created_at))
        .all()
    )

    # -----------------------------
    # BUILD PDF
    # -----------------------------
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter
    y = height - 50

    # Title
    c.setFont("Helvetica-Bold", 18)
    c.drawString(50, y, "JADE – Engagement & Retention Report")
    y -= 30

    # Date range
    c.setFont("Helvetica", 12)
    c.drawString(50, y, f"Window: {start_dt.date()} to {(end_dt - timedelta(days=1)).date()}")
    y -= 25

    # -----------------------------
    # Summary
    # -----------------------------
    c.setFont("Helvetica-Bold", 14)
    c.drawString(50, y, "Summary")
    y -= 20
    c.setFont("Helvetica", 12)

    summary_lines = [
        f"Total Customers: {total_customers}",
        f"Active Users (in window): {active_users}",
        f"New Customers (in window): {new_users}",
        f"Total Appointments (in window): {total_appointments}",
        f"Returning Users (in window): {returning_users}",
        f"Retention Rate (%): {round(retention_rate, 2)}",
        f"Total Salons: {total_salons}",
    ]

    for line in summary_lines:
        c.drawString(50, y, line)
        y -= 18

    # Page break if needed
    if y < 120:
        c.showPage()
        y = height - 50

    # -----------------------------
    # Appointments per Day
    # -----------------------------
    c.setFont("Helvetica-Bold", 14)
    c.drawString(50, y, "Appointments per Day")
    y -= 20
    c.setFont("Helvetica-Bold", 12)
    c.drawString(50, y, "Date")
    c.drawString(200, y, "Appointments")
    y -= 16
    c.setFont("Helvetica", 12)

    for r in appt_trend:
        c.drawString(50, y, str(r.day))
        c.drawString(200, y, str(int(r.count)))
        y -= 16
        if y < 80:
            c.showPage(); y = height - 50

    # -----------------------------
    # Returning Users per Day
    # -----------------------------
    c.setFont("Helvetica-Bold", 14)
    c.drawString(50, y, "Returning Users per Day")
    y -= 20
    c.setFont("Helvetica-Bold", 12)
    c.drawString(50, y, "Date")
    c.drawString(200, y, "Returning Users")
    y -= 16
    c.setFont("Helvetica", 12)

    for r in returning_trend:
        c.drawString(50, y, str(r.day))
        c.drawString(200, y, str(int(r.returning)))
        y -= 16
        if y < 80:
            c.showPage(); y = height - 50

    # -----------------------------
    # Cohort Retention Monthly
    # -----------------------------
    c.setFont("Helvetica-Bold", 14)
    c.drawString(50, y, "Cohort Retention (Monthly)")
    y -= 20

    c.setFont("Helvetica-Bold", 12)
    c.drawString(50, y, "Month")
    c.drawString(200, y, "Count")
    y -= 16

    c.setFont("Helvetica", 12)
    for r in cohort_rows:
        c.drawString(50, y, str(r.month))
        c.drawString(200, y, str(int(r.count)))
        y -= 16
        if y < 80:
            c.showPage(); y = height - 50

    # Finish
    c.showPage()
    c.save()
    buffer.seek(0)

    filename = f"jade_engagement_report_{start_dt.date()}_{end_dt.date()}.pdf"

    return send_file(
        buffer,
        mimetype="application/pdf",
        as_attachment=True,
        download_name=filename,
    )
