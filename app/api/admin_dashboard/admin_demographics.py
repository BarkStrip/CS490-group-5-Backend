

import io
from datetime import datetime, timedelta

from flask import Blueprint, jsonify, send_file
from app.extensions import db
from sqlalchemy import func, case
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas

from app.models import (
    Appointment,
    Salon,
    Customers,
    LoyaltyAccount,
    LoyaltyProgram,
    LoyaltyTransaction,
)

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
        db.session.query(Salon.city, func.count(Appointment.id))
        .join(Salon, Appointment.salon_id == Salon.id)
        .group_by(Salon.city)
        .all()
    )

    return jsonify(
        [{"name": city or "Unknown", "value": int(count)} for city, count in rows]
    )


# ---------------------------------------------------------
# 2) LOYALTY SEGMENTS (Loyalty vs Guests)
# ---------------------------------------------------------
@admin_demographics_bp.route("/loyalty-segments", methods=["GET"])
def loyalty_segments():

    total_users = db.session.query(func.count(Customers.id)).scalar() or 0

    loyalty_users = (
        db.session.query(func.count(func.distinct(LoyaltyAccount.user_id))).scalar()
        or 0
    )

    guest_users = total_users - loyalty_users

    return jsonify(
        [
            {"segment": "Loyalty Members", "count": int(loyalty_users)},
            {"segment": "Guests", "count": int(guest_users)},
        ]
    )


# ---------------------------------------------------------
# 3) GENDER DISTRIBUTION
# ---------------------------------------------------------
@admin_demographics_bp.route("/gender", methods=["GET"])
def gender_distribution():

    rows = (
        db.session.query(Customers.gender, func.count(Customers.id))
        .filter(Customers.gender.isnot(None))
        .filter(Customers.gender != "")
        .group_by(Customers.gender)
        .all()
    )

    return jsonify(
        [{"gender": gender or "Unknown", "count": int(count)} for gender, count in rows]
    )


# ---------------------------------------------------------
# 4) AGE GROUP DISTRIBUTION
# ---------------------------------------------------------
@admin_demographics_bp.route("/age-groups", methods=["GET"])
def age_groups():

    rows = (
        db.session.query(
            case(
                (Customers.age < 18, "Under 18"),
                (Customers.age.between(18, 24), "18-24"),
                (Customers.age.between(25, 34), "25-34"),
                (Customers.age.between(35, 44), "35-44"),
                (Customers.age.between(45, 54), "45-54"),
                else_="55+",
            ).label("age_group"),
            func.count(Customers.id),
        )
        .filter(Customers.age.isnot(None))
        .group_by("age_group")
        .order_by(func.count(Customers.id).desc())
        .all()
    )

    return jsonify([{"age_group": group, "count": int(count)} for group, count in rows])



# app/routes/admin_demographics.py  (only loyalty_summary updated)

from datetime import datetime, timedelta
from flask import Blueprint, jsonify
from app.extensions import db
from sqlalchemy import func, case
from app.models import (
    Appointment,
    Salon,
    Customers,
    LoyaltyAccount,
    LoyaltyProgram,
    LoyaltyTransaction,
)

...

# ---------------------------------------------------------
# 5) LOYALTY SUMMARY (usage & effectiveness)
# ---------------------------------------------------------
@admin_demographics_bp.route("/loyalty-summary", methods=["GET"])
def loyalty_summary():
    """
    High-level loyalty usage metrics for Demographics page.

    - totalMembers: total loyalty accounts
    - activeLoyaltySalons: salons that have an active loyalty program
    - totalPointsBalance: sum of all member point balances
    - avgPointsPerMember: totalPointsBalance / totalMembers

    - activeMembers90d: members with at least one transaction in last 90 days
    - dormantMembers90d: totalMembers - activeMembers90d
    - engagementRate90d: activeMembers90d / totalMembers

    - transactionsLast90d: number of loyalty transactions in last 90 days

    - pointsEarned90d: sum of positive points_change in last 90 days
    - pointsRedeemed90d: sum of |negative points_change| in last 90 days
    - redemptionRate90d: pointsRedeemed90d / (pointsEarned90d + pointsRedeemed90d)
      -> always between 0 and 1, so it never shows > 100%
    """

    # ---------- members & balances ----------
    total_members = (
        db.session.query(func.count(LoyaltyAccount.id)).scalar() or 0
    )

    total_points_balance = (
        db.session.query(
            func.coalesce(func.sum(LoyaltyAccount.points), 0)
        ).scalar()
        or 0
    )

    avg_points_per_member = (
        float(total_points_balance) / float(total_members)
        if total_members > 0
        else 0.0
    )

    # ---------- program coverage ----------
    active_loyalty_salons = (
        db.session.query(
            func.count(func.distinct(LoyaltyProgram.salon_id))
        )
        .filter(LoyaltyProgram.active == 1)
        .scalar()
        or 0
    )

    # ---------- activity window: last 90 days ----------
    now = datetime.utcnow()
    cutoff_90 = now - timedelta(days=90)

    # members with at least 1 transaction in 90 days
    active_members_90 = (
        db.session.query(
            func.count(func.distinct(LoyaltyTransaction.loyalty_account_id))
        )
        .filter(LoyaltyTransaction.created_at >= cutoff_90)
        .scalar()
        or 0
    )

    dormant_members_90 = max(total_members - active_members_90, 0)

    engagement_rate_90 = (
        float(active_members_90) / float(total_members)
        if total_members > 0
        else 0.0
    )

    transactions_90 = (
        db.session.query(func.count(LoyaltyTransaction.id))
        .filter(LoyaltyTransaction.created_at >= cutoff_90)
        .scalar()
        or 0
    )

    # ---------- points flow in last 90 days ----------
    points_earned_90 = (
        db.session.query(
            func.coalesce(
                func.sum(
                    case(
                        (LoyaltyTransaction.points_change > 0, LoyaltyTransaction.points_change),
                        else_=0,
                    )
                ),
                0,
            )
        )
        .filter(LoyaltyTransaction.created_at >= cutoff_90)
        .scalar()
        or 0
    )

    points_redeemed_90 = (
        db.session.query(
            func.coalesce(
                func.sum(
                    case(
                        (
                            LoyaltyTransaction.points_change < 0,
                            -LoyaltyTransaction.points_change,
                        ),
                        else_=0,
                    )
                ),
                0,
            )
        )
        .filter(LoyaltyTransaction.created_at >= cutoff_90)
        .scalar()
        or 0
    )

    denom = float(points_earned_90 + points_redeemed_90)
    redemption_rate_90 = float(points_redeemed_90) / denom if denom > 0 else 0.0

    return jsonify(
        {
            "totalMembers": int(total_members),
            "activeLoyaltySalons": int(active_loyalty_salons),
            "totalPointsBalance": float(total_points_balance),
            "avgPointsPerMember": round(avg_points_per_member, 2),

            "activeMembers90d": int(active_members_90),
            "dormantMembers90d": int(dormant_members_90),
            "engagementRate90d": round(engagement_rate_90, 2),
            "transactionsLast90d": int(transactions_90),

            "pointsEarned90d": float(points_earned_90),
            "pointsRedeemed90d": float(points_redeemed_90),
            "redemptionRate90d": round(redemption_rate_90, 2),
        }
    )

# ---------------------------------------------------------
# 6) DEMOGRAPHICS REPORT PDF
# ---------------------------------------------------------
@admin_demographics_bp.route("/report-pdf", methods=["GET"])
def demographics_report_pdf():
    """
    Generate a PDF summary for the Demographics page:

      - Loyalty summary (coverage, activity, redemption)
      - Appointments by city
      - Loyalty members vs guests
      - Gender distribution
      - Age group distribution
    """

    # ----- loyalty summary (reuse same logic as above, but keep as raw values) -----
    total_members = db.session.query(func.count(LoyaltyAccount.id)).scalar() or 0

    total_points_balance = (
        db.session.query(func.coalesce(func.sum(LoyaltyAccount.points), 0)).scalar() or 0
    )

    avg_points_per_member = (
        float(total_points_balance) / float(total_members) if total_members > 0 else 0.0
    )

    active_loyalty_salons = (
        db.session.query(func.count(func.distinct(LoyaltyProgram.salon_id)))
        .filter(LoyaltyProgram.active == 1)
        .scalar()
        or 0
    )

    now = datetime.utcnow()
    cutoff_90 = now - timedelta(days=90)

    active_members_90 = (
        db.session.query(
            func.count(func.distinct(LoyaltyTransaction.loyalty_account_id))
        )
        .filter(LoyaltyTransaction.created_at >= cutoff_90)
        .scalar()
        or 0
    )
    dormant_members_90 = max(total_members - active_members_90, 0)
    engagement_rate_90 = (
        float(active_members_90) / float(total_members) if total_members > 0 else 0.0
    )

    transactions_90 = (
        db.session.query(func.count(LoyaltyTransaction.id))
        .filter(LoyaltyTransaction.created_at >= cutoff_90)
        .scalar()
        or 0
    )

    points_earned_90 = (
        db.session.query(
            func.coalesce(
                func.sum(
                    case(
                        (
                            LoyaltyTransaction.points_change > 0,
                            LoyaltyTransaction.points_change,
                        ),
                        else_=0,
                    )
                ),
                0,
            )
        )
        .filter(LoyaltyTransaction.created_at >= cutoff_90)
        .scalar()
        or 0
    )

    points_redeemed_90 = (
        db.session.query(
            func.coalesce(
                func.sum(
                    case(
                        (
                            LoyaltyTransaction.points_change < 0,
                            -LoyaltyTransaction.points_change,
                        ),
                        else_=0,
                    )
                ),
                0,
            )
        )
        .filter(LoyaltyTransaction.created_at >= cutoff_90)
        .scalar()
        or 0
    )

    denom = float(points_earned_90 + points_redeemed_90)
    redemption_rate_90 = float(points_redeemed_90) / denom if denom > 0 else 0.0

    # ----- appointments by city -----
    city_rows = (
        db.session.query(Salon.city, func.count(Appointment.id))
        .join(Salon, Appointment.salon_id == Salon.id)
        .group_by(Salon.city)
        .all()
    )
    city_data = [
        {"name": city or "Unknown", "value": int(count)} for city, count in city_rows
    ]

    # ----- loyalty segments -----
    total_users = db.session.query(func.count(Customers.id)).scalar() or 0
    loyalty_users = (
        db.session.query(func.count(func.distinct(LoyaltyAccount.user_id))).scalar()
        or 0
    )
    guest_users = total_users - loyalty_users

    # ----- gender distribution -----
    gender_rows = (
        db.session.query(Customers.gender, func.count(Customers.id))
        .filter(Customers.gender.isnot(None))
        .filter(Customers.gender != "")
        .group_by(Customers.gender)
        .all()
    )
    gender_data = [
        {"gender": gender or "Unknown", "count": int(count)}
        for gender, count in gender_rows
    ]

    # ----- age group distribution -----
    age_rows = (
        db.session.query(
            case(
                (Customers.age < 18, "Under 18"),
                (Customers.age.between(18, 24), "18-24"),
                (Customers.age.between(25, 34), "25-34"),
                (Customers.age.between(35, 44), "35-44"),
                (Customers.age.between(45, 54), "45-54"),
                else_="55+",
            ).label("age_group"),
            func.count(Customers.id),
        )
        .filter(Customers.age.isnot(None))
        .group_by("age_group")
        .order_by(func.count(Customers.id).desc())
        .all()
    )
    age_data = [{"age_group": group, "count": int(count)} for group, count in age_rows]

    # ----- build PDF -----
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter
    y = height - inch

    # Title
    c.setFont("Helvetica-Bold", 18)
    c.drawString(inch, y, "JADE – Demographics & Loyalty Report")
    y -= 0.4 * inch

    c.setFont("Helvetica", 11)
    c.drawString(
        inch,
        y,
        "Loyalty activity window: last 90 days   |   User & booking demographics (all-time)",
    )
    y -= 0.3 * inch

    # ----- Loyalty Coverage -----
    c.setFont("Helvetica-Bold", 14)
    c.drawString(inch, y, "Loyalty Coverage")
    y -= 0.25 * inch
    c.setFont("Helvetica", 11)
    coverage_lines = [
        f"Total members: {total_members}",
        f"Salons with loyalty: {active_loyalty_salons}",
        f"Total points balance: {int(total_points_balance)} pts",
        f"Average points per member: {avg_points_per_member:.1f} pts",
    ]
    for line in coverage_lines:
        c.drawString(inch, y, line)
        y -= 0.2 * inch

    if y < inch:
        c.showPage()
        y = height - inch

    # ----- Member Activity (Last 90 Days) -----
    c.setFont("Helvetica-Bold", 14)
    c.drawString(inch, y, "Member Activity (Last 90 Days)")
    y -= 0.25 * inch
    c.setFont("Helvetica", 11)
    activity_lines = [
        f"Active members: {active_members_90}",
        f"Dormant members: {dormant_members_90}",
        f"Engagement rate: {engagement_rate_90*100:.0f}%",
        f"Transactions (90d): {transactions_90}",
    ]
    for line in activity_lines:
        c.drawString(inch, y, line)
        y -= 0.2 * inch

    if y < inch:
        c.showPage()
        y = height - inch

    # ----- Points & Redemption (Last 90 Days) -----
    c.setFont("Helvetica-Bold", 14)
    c.drawString(inch, y, "Points & Redemption (Last 90 Days)")
    y -= 0.25 * inch
    c.setFont("Helvetica", 11)
    redemption_lines = [
        f"Points earned: {int(points_earned_90)} pts",
        f"Points redeemed: {int(points_redeemed_90)} pts",
        f"Redemption rate: {redemption_rate_90*100:.0f}%",
    ]
    for line in redemption_lines:
        c.drawString(inch, y, line)
        y -= 0.2 * inch

    if y < inch:
        c.showPage()
        y = height - inch

    # ----- Appointments by City -----
    c.setFont("Helvetica-Bold", 14)
    c.drawString(inch, y, "Appointments by City")
    y -= 0.25 * inch
    c.setFont("Helvetica-Bold", 11)
    c.drawString(inch, y, "City")
    c.drawString(3 * inch, y, "Appointments")
    y -= 0.2 * inch
    c.setFont("Helvetica", 11)

    for row in city_data:
        c.drawString(inch, y, row["name"])
        c.drawString(3 * inch, y, str(row["value"]))
        y -= 0.18 * inch
        if y < inch:
            c.showPage()
            y = height - inch
            c.setFont("Helvetica", 11)

    # ----- Loyalty Members vs Guests -----
    c.setFont("Helvetica-Bold", 14)
    c.drawString(inch, y, "Loyalty Members vs Guests (Customers)")
    y -= 0.25 * inch
    c.setFont("Helvetica-Bold", 11)
    c.drawString(inch, y, "Segment")
    c.drawString(3 * inch, y, "Customers")
    y -= 0.2 * inch
    c.setFont("Helvetica", 11)

    c.drawString(inch, y, "Loyalty Members")
    c.drawString(3 * inch, y, str(loyalty_users))
    y -= 0.18 * inch
    c.drawString(inch, y, "Guests")
    c.drawString(3 * inch, y, str(guest_users))
    y -= 0.25 * inch

    if y < inch:
        c.showPage()
        y = height - inch

    # ----- Gender Distribution -----
    c.setFont("Helvetica-Bold", 14)
    c.drawString(inch, y, "Gender Distribution")
    y -= 0.25 * inch
    c.setFont("Helvetica-Bold", 11)
    c.drawString(inch, y, "Gender")
    c.drawString(3 * inch, y, "Customers")
    y -= 0.2 * inch
    c.setFont("Helvetica", 11)

    for row in gender_data:
        c.drawString(inch, y, row["gender"])
        c.drawString(3 * inch, y, str(row["count"]))
        y -= 0.18 * inch
        if y < inch:
            c.showPage()
            y = height - inch
            c.setFont("Helvetica", 11)

    # ----- Age Group Distribution -----
    c.setFont("Helvetica-Bold", 14)
    c.drawString(inch, y, "Age Group Distribution")
    y -= 0.25 * inch
    c.setFont("Helvetica-Bold", 11)
    c.drawString(inch, y, "Age group")
    c.drawString(3 * inch, y, "Customers")
    y -= 0.2 * inch
    c.setFont("Helvetica", 11)

    for row in age_data:
        c.drawString(inch, y, row["age_group"])
        c.drawString(3 * inch, y, str(row["count"]))
        y -= 0.18 * inch
        if y < inch:
            c.showPage()
            y = height - inch
            c.setFont("Helvetica", 11)

    c.showPage()
    c.save()
    buffer.seek(0)

    filename = f"jade_demographics_report_{datetime.utcnow().date()}.pdf"
    return send_file(
        buffer,
        mimetype="application/pdf",
        as_attachment=True,
        download_name=filename,
    )