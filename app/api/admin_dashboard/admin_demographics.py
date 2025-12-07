# app/routes/admin_demographics.py

from flask import Blueprint, jsonify
from app.extensions import db
from sqlalchemy import func, case
from app.models import Appointment, Salon, Customers, LoyaltyAccount

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

