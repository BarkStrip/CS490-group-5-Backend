import io
from datetime import datetime, timedelta

from flask import Blueprint, jsonify, request, send_file
from sqlalchemy import func
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas

from app.extensions import db
from app.models import Appointment, Salon, SalonVerify
from sqlalchemy import func

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
    """Appointments per day in a date window, including 0-count days."""

    today = datetime.utcnow().date()

    # --- optional query params ---
    from_str = request.args.get("from")
    to_str = request.args.get("to")
    salon_id = request.args.get("salonId", type=int)

    # start date (default: last 7 days)
    if from_str:
        start_date = datetime.strptime(from_str, "%Y-%m-%d").date()
    else:
        start_date = today - timedelta(days=6)

    # end date (default: today)
    if to_str:
        end_date = datetime.strptime(to_str, "%Y-%m-%d").date()
    else:
        end_date = today

    upper_bound = end_date + timedelta(days=1)

    q = (
        db.session.query(
            func.date(Appointment.created_at).label("day"),
            func.count(Appointment.id).label("count"),
        )
        .filter(Appointment.created_at >= start_date)
        .filter(Appointment.created_at < upper_bound)
    )

    if salon_id:
        q = q.filter(Appointment.salon_id == salon_id)

    rows = (
        q.group_by(func.date(Appointment.created_at))
        .order_by(func.date(Appointment.created_at))
        .all()
    )

    # map: date -> count
    counts_by_day = {r.day: int(r.count) for r in rows}

    # build continuous range, fill missing with 0
    data = []
    current = start_date
    while current <= end_date:
        data.append(
            {
                "day": current.strftime("%Y-%m-%d"),
                "count": counts_by_day.get(current, 0),
            }
        )
        current += timedelta(days=1)

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

    today = datetime.utcnow().date()
    start_date = today - timedelta(days=6)
    start_dt = datetime.combine(start_date, datetime.min.time())
    upper_bound = datetime.combine(today + timedelta(days=1), datetime.min.time())

    rows = (
        db.session.query(
            func.date(Customers.created_at).label("day"),
            func.count(Customers.id).label("count"),
        )
        .filter(Customers.created_at >= start_dt)
        .filter(Customers.created_at < upper_bound)
        .group_by(func.date(Customers.created_at))
        .order_by(func.date(Customers.created_at))
        .all()
    )

    counts_by_day = {r.day: int(r.count) for r in rows}

    data = []
    current = start_date
    while current <= today:
        data.append(
            {
                "day": current.strftime("%Y-%m-%d"),
                "count": counts_by_day.get(current, 0),
            }
        )
        current += timedelta(days=1)

    return jsonify({"customers": data}), 200



@admin_salon_activity_bp.route("/salons-trend", methods=["GET"])
def salons_trend():
    from app.models import Salon

    today = datetime.utcnow().date()
    start_date = today - timedelta(days=29)  # last 30 days (today included)
    
    start_dt = datetime.combine(start_date, datetime.min.time())
    upper_bound = datetime.combine(today + timedelta(days=1), datetime.min.time())

    rows = (
        db.session.query(
            func.date(Salon.created_at).label("day"),
            func.count(Salon.id).label("count"),
        )
        .filter(Salon.created_at >= start_dt)
        .filter(Salon.created_at < upper_bound)
        .group_by(func.date(Salon.created_at))
        .order_by(func.date(Salon.created_at))
        .all()
    )

    # Map of day -> count
    counts_by_day = {r.day: int(r.count) for r in rows}

    # Build continuous date series for last 30 days
    data = []
    current = start_date
    while current <= today:
        data.append(
            {
                "day": current.strftime("%Y-%m-%d"),
                "count": counts_by_day.get(current, 0),  # default 0
            }
        )
        current += timedelta(days=1)

    return jsonify({"salons": data}), 200



@admin_salon_activity_bp.route("/peak-hours", methods=["GET"])
def get_peak_hours():
    """
    Peak-hour analytics based on appointment start time.

    Query params (all optional):
      - from: start date (YYYY-MM-DD), default: today - 29 days (last 30 days)
      - to:   end date   (YYYY-MM-DD), default: today
      - salonId: filter by a specific salon_id

    Returns:
      {
        "byHour": [ { "hour": 9, "count": 12 }, ... ],
        "byDowHour": [ { "dow": "Mon", "hour": 10, "count": 5 }, ... ]
      }
    """
    today = datetime.utcnow().date()

    from_str = request.args.get("from")
    to_str = request.args.get("to")

    if from_str:
        start_date = datetime.strptime(from_str, "%Y-%m-%d").date()
    else:
        start_date = today - timedelta(days=29)  # last 30 days

    if to_str:
        end_date = datetime.strptime(to_str, "%Y-%m-%d").date()
    else:
        end_date = today

    upper_bound = end_date + timedelta(days=1)
    salon_id = request.args.get("salonId", type=int)

    # base query: only appointments with a real start time in the window
    base_q = db.session.query(Appointment).filter(
        Appointment.start_at.isnot(None),
        Appointment.start_at >= start_date,
        Appointment.start_at < upper_bound,
    )

    if salon_id:
        base_q = base_q.filter(Appointment.salon_id == salon_id)

    # --- 1) counts by HOUR ---
    by_hour_rows = (
        db.session.query(
            func.hour(Appointment.start_at).label("hour"),
            func.count(Appointment.id).label("count"),
        )
        .select_from(Appointment)
        .filter(Appointment.id.in_(base_q.with_entities(Appointment.id)))
        .group_by(func.hour(Appointment.start_at))
        .order_by(func.hour(Appointment.start_at))
        .all()
    )

    by_hour = [{"hour": int(r.hour), "count": int(r.count)} for r in by_hour_rows]

    # --- 2) counts by DAY-OF-WEEK + HOUR ---
    # MySQL DAYOFWEEK: 1=Sunday ... 7=Saturday
    DOW_MAP = {
        1: "Sun",
        2: "Mon",
        3: "Tue",
        4: "Wed",
        5: "Thu",
        6: "Fri",
        7: "Sat",
    }

    by_dow_hour_rows = (
        db.session.query(
            func.dayofweek(Appointment.start_at).label("dow_idx"),
            func.hour(Appointment.start_at).label("hour"),
            func.count(Appointment.id).label("count"),
        )
        .select_from(Appointment)
        .filter(Appointment.id.in_(base_q.with_entities(Appointment.id)))
        .group_by(func.dayofweek(Appointment.start_at), func.hour(Appointment.start_at))
        .order_by(func.dayofweek(Appointment.start_at), func.hour(Appointment.start_at))
        .all()
    )

    by_dow_hour = [
        {
            "dow": DOW_MAP.get(int(r.dow_idx), str(r.dow_idx)),
            "hour": int(r.hour),
            "count": int(r.count),
        }
        for r in by_dow_hour_rows
    ]

    return jsonify({"byHour": by_hour, "byDowHour": by_dow_hour}), 200



@admin_salon_activity_bp.route("/wait-time", methods=["GET"])
def get_wait_time_metrics():
    """
    Basic wait-time health metric.

    Uses difference between appointment.created_at (when booked)
    and start_at (when service actually started), for COMPLETED appointments.
    Filters out negative values and anything over 4 hours (240 minutes).
    """
    MAX_MINUTES = 240

    q = db.session.query(
        Appointment.created_at,
        Appointment.start_at,
    ).filter(
        Appointment.created_at.isnot(None),
        Appointment.start_at.isnot(None),
        Appointment.status == "COMPLETED",
    )

    waits = []
    for created_at, start_at in q.all():
        diff = (start_at - created_at).total_seconds() / 60.0
        if 0 <= diff <= MAX_MINUTES:
            waits.append(diff)

    avg_wait = round(sum(waits) / len(waits), 1) if waits else 0

    return jsonify({"avg_wait_minutes": avg_wait, "sample_size": len(waits)}), 200



# ---------------------------------------------------------
# 8. SALON ACTIVITY REPORT PDF
# ---------------------------------------------------------
@admin_salon_activity_bp.route("/report-pdf", methods=["GET"])
def salon_activity_report_pdf():
    """
    Generate a PDF summary for the Salon Activity dashboard.

    - Pending verifications
    - Top salons
    - Avg appointment duration + avg wait time
    - Appointment trends (last 7 days)
    - Bookings by hour (last 30 days)
    - New customer registrations (last 7 days)
    - New salon registrations (last 30 days)

    Optional query param:
      ?salonId=ID  -> filters appointment-based metrics for a single salon
    """
    salon_id = request.args.get("salonId", type=int)
    today = datetime.utcnow().date()

    # ---------------- SUMMARY BLOCK ----------------
    # 1) Pending verifications
    pending_rows = (
        db.session.query(
            SalonVerify.id.label("verification_id"),
            Salon.name.label("name"),
        )
        .join(Salon, SalonVerify.salon_id == Salon.id)
        .filter(SalonVerify.status == "PENDING")
        .all()
    )
    pending_count = len(pending_rows)

    # 2) Top salons (same as /top)
    top_rows = (
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
    top_salons = [{"name": r.name, "count": int(r.count)} for r in top_rows]

    # 3) Avg appointment duration (same logic as /metrics)
    MINUTES_LIMIT = 300
    dur_rows = (
        db.session.query(Appointment.start_at, Appointment.end_at, Appointment.status)
        .filter(Appointment.start_at.isnot(None))
        .filter(Appointment.end_at.isnot(None))
        .filter(Appointment.status == "COMPLETED")
        .all()
    )
    durations = []
    for r in dur_rows:
        if r.start_at and r.end_at:
            diff = (r.end_at - r.start_at).total_seconds() / 60
            if 0 < diff <= MINUTES_LIMIT:
                durations.append(diff)
    avg_duration = round(sum(durations) / len(durations), 1) if durations else 0

    # 4) Avg wait time (same logic as /wait-time)
    MAX_WAIT_MIN = 240
    wait_q = db.session.query(
        Appointment.created_at,
        Appointment.start_at,
    ).filter(
        Appointment.created_at.isnot(None),
        Appointment.start_at.isnot(None),
        Appointment.status == "COMPLETED",
    )
    waits = []
    for created_at, start_at in wait_q.all():
        diff = (start_at - created_at).total_seconds() / 60.0
        if 0 <= diff <= MAX_WAIT_MIN:
            waits.append(diff)
    avg_wait = round(sum(waits) / len(waits), 1) if waits else 0

    # ---------------- TRENDS: APPOINTMENTS (7 days) ----------------
    start_7 = today - timedelta(days=6)
    start_7_dt = datetime.combine(start_7, datetime.min.time())
    end_7_dt = datetime.combine(today + timedelta(days=1), datetime.min.time())

    appt_q = (
        db.session.query(
            func.date(Appointment.created_at).label("day"),
            func.count(Appointment.id).label("count"),
        )
        .filter(Appointment.created_at >= start_7_dt)
        .filter(Appointment.created_at < end_7_dt)
    )
    if salon_id:
        appt_q = appt_q.filter(Appointment.salon_id == salon_id)

    appt_rows = (
        appt_q.group_by(func.date(Appointment.created_at))
        .order_by(func.date(Appointment.created_at))
        .all()
    )
    appt_counts = {r.day: int(r.count) for r in appt_rows}
    appt_trend = []
    current = start_7
    while current <= today:
        appt_trend.append(
            {
                "day": current.strftime("%Y-%m-%d"),
                "count": appt_counts.get(current, 0),
            }
        )
        current += timedelta(days=1)

    # ---------------- BOOKINGS BY HOUR (30 days) ----------------
    start_30 = today - timedelta(days=29)
    start_30_dt = datetime.combine(start_30, datetime.min.time())
    end_30_dt = datetime.combine(today + timedelta(days=1), datetime.min.time())

    base_q = db.session.query(Appointment).filter(
        Appointment.start_at.isnot(None),
        Appointment.start_at >= start_30_dt,
        Appointment.start_at < end_30_dt,
    )
    if salon_id:
        base_q = base_q.filter(Appointment.salon_id == salon_id)

    by_hour_rows = (
        db.session.query(
            func.hour(Appointment.start_at).label("hour"),
            func.count(Appointment.id).label("count"),
        )
        .select_from(Appointment)
        .filter(Appointment.id.in_(base_q.with_entities(Appointment.id)))
        .group_by(func.hour(Appointment.start_at))
        .order_by(func.hour(Appointment.start_at))
        .all()
    )
    by_hour = [{"hour": int(r.hour), "count": int(r.count)} for r in by_hour_rows]

    # ---------------- NEW CUSTOMERS 7 days ----------------
    from app.models import Customers

    cust_rows = (
        db.session.query(
            func.date(Customers.created_at).label("day"),
            func.count(Customers.id).label("count"),
        )
        .filter(Customers.created_at >= start_7_dt)
        .filter(Customers.created_at < end_7_dt)
        .group_by(func.date(Customers.created_at))
        .order_by(func.date(Customers.created_at))
        .all()
    )
    cust_counts = {r.day: int(r.count) for r in cust_rows}
    cust_trend = []
    current = start_7
    while current <= today:
        cust_trend.append(
            {
                "day": current.strftime("%Y-%m-%d"),
                "count": cust_counts.get(current, 0),
            }
        )
        current += timedelta(days=1)

    # ---------------- NEW SALONS 30 days ----------------
    salon_rows = (
        db.session.query(
            func.date(Salon.created_at).label("day"),
            func.count(Salon.id).label("count"),
        )
        .filter(Salon.created_at >= start_30_dt)
        .filter(Salon.created_at < end_30_dt)
        .group_by(func.date(Salon.created_at))
        .order_by(func.date(Salon.created_at))
        .all()
    )
    salon_counts = {r.day: int(r.count) for r in salon_rows}
    salon_trend = []
    current = start_30
    while current <= today:
        salon_trend.append(
            {
                "day": current.strftime("%Y-%m-%d"),
                "count": salon_counts.get(current, 0),
            }
        )
        current += timedelta(days=1)

    # ---------------- BUILD PDF ----------------
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter
    y = height - inch

    # Title
    c.setFont("Helvetica-Bold", 18)
    c.drawString(inch, y, "JADE – Salon Activity Report")
    y -= 0.4 * inch

    c.setFont("Helvetica", 11)
    c.drawString(
        inch,
        y,
        f"Appointments window: {start_7} to {today}  |  Peak & new salons: last 30 days",
    )
    y -= 0.25 * inch
    if salon_id:
        c.drawString(inch, y, f"Filtered for Salon ID: {salon_id}")
        y -= 0.25 * inch

    # -------- Summary section --------
    y -= 0.1 * inch
    c.setFont("Helvetica-Bold", 14)
    c.drawString(inch, y, "Summary")
    y -= 0.3 * inch
    c.setFont("Helvetica", 11)

    summary_lines = [
        f"Pending verifications: {pending_count}",
        f"Average appointment duration (min): {avg_duration}",
        f"Average wait time before appointment (min): {avg_wait}",
    ]
    for line in summary_lines:
        c.drawString(inch, y, line)
        y -= 0.2 * inch

    # Top salons
    if top_salons:
        c.drawString(inch, y, "Top salons (by bookings):")
        y -= 0.2 * inch
        for s in top_salons:
            c.drawString(
                inch + 15,
                y,
                f"- {s['name']}: {s['count']} bookings",
            )
            y -= 0.18 * inch

    if y < inch:
        c.showPage()
        y = height - inch

    # -------- Appointment trends (7 days) --------
    c.setFont("Helvetica-Bold", 14)
    c.drawString(inch, y, "Appointment Trends (Last 7 Days)")
    y -= 0.3 * inch
    c.setFont("Helvetica-Bold", 11)
    c.drawString(inch, y, "Date")
    c.drawString(3 * inch, y, "Bookings")
    y -= 0.2 * inch
    c.setFont("Helvetica", 11)

    for row in appt_trend:
        c.drawString(inch, y, row["day"])
        c.drawString(3 * inch, y, str(row["count"]))
        y -= 0.18 * inch
        if y < inch:
            c.showPage()
            y = height - inch
            c.setFont("Helvetica", 11)

    # -------- Bookings by hour (30 days) --------
    c.setFont("Helvetica-Bold", 14)
    c.drawString(inch, y, "Bookings by Hour (Last 30 Days)")
    y -= 0.3 * inch
    c.setFont("Helvetica-Bold", 11)
    c.drawString(inch, y, "Hour")
    c.drawString(3 * inch, y, "Bookings")
    y -= 0.2 * inch
    c.setFont("Helvetica", 11)

    for row in by_hour:
        c.drawString(inch, y, f"{row['hour']:02d}:00")
        c.drawString(3 * inch, y, str(row["count"]))
        y -= 0.18 * inch
        if y < inch:
            c.showPage()
            y = height - inch
            c.setFont("Helvetica", 11)

    # -------- New customers (7 days) --------
    c.setFont("Helvetica-Bold", 14)
    c.drawString(inch, y, "New Customer Registrations (Last 7 Days)")
    y -= 0.3 * inch
    c.setFont("Helvetica-Bold", 11)
    c.drawString(inch, y, "Date")
    c.drawString(3 * inch, y, "New customers")
    y -= 0.2 * inch
    c.setFont("Helvetica", 11)

    for row in cust_trend:
        c.drawString(inch, y, row["day"])
        c.drawString(3 * inch, y, str(row["count"]))
        y -= 0.18 * inch
        if y < inch:
            c.showPage()
            y = height - inch
            c.setFont("Helvetica", 11)

    # -------- New salons (30 days) --------
    c.setFont("Helvetica-Bold", 14)
    c.drawString(inch, y, "New Salon Registrations (Last 30 Days)")
    y -= 0.3 * inch
    c.setFont("Helvetica-Bold", 11)
    c.drawString(inch, y, "Date")
    c.drawString(3 * inch, y, "New salons")
    y -= 0.2 * inch
    c.setFont("Helvetica", 11)

    for row in salon_trend:
        c.drawString(inch, y, row["day"])
        c.drawString(3 * inch, y, str(row["count"]))
        y -= 0.18 * inch
        if y < inch:
            c.showPage()
            y = height - inch
            c.setFont("Helvetica", 11)

    c.showPage()
    c.save()
    buffer.seek(0)

    filename = f"jade_salon_activity_report_{today}.pdf"
    return send_file(
        buffer,
        mimetype="application/pdf",
        as_attachment=True,
        download_name=filename,
    )
