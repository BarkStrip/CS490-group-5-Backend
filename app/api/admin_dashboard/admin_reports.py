# app/routes/admin_reports_export.py

import io
from datetime import datetime, timedelta

import pandas as pd
from flask import Blueprint, request, send_file
from sqlalchemy import func, case

from app.extensions import db
from app.models import (
    Appointment,
    Salon,
    Customers,
    LoyaltyAccount,
    LoyaltyProgram,
    LoyaltyTransaction,
    Order,  # if you don't have this yet, comment it out & the code will still work
)

admin_reports_export_bp = Blueprint(
    "admin_reports_export_bp",
    __name__,
    url_prefix="/api/admin/reports",
)

# -------------------------------------------------------------------
#  ANALYTICS EXPORT (match Engagement & Retention dashboard)
# -------------------------------------------------------------------

def build_analytics_export():
    """
    Exports the same conceptual data as the Analytics dashboard:
      - summary cards (active users, customers, appointments, salons, retention)
      - appointments (last 30 days)
      - returning users (last 30 days)
      - cohort retention by month (last ~3 months)
    """

    today = datetime.utcnow().date()
    since_30d = today - timedelta(days=30)

    # ---------- SUMMARY CARDS ----------

    # Active users (customers with at least one appt in last 30 days)
    active_users_30 = (
        db.session.query(func.count(func.distinct(Appointment.customer_id)))
        .filter(Appointment.start_time >= since_30d)
        .scalar()
        or 0
    )

    # Total customers
    total_customers = db.session.query(func.count(Customers.id)).scalar() or 0

    # New customers in last 30 days (needs Customers.created_at)
    try:
        new_customers_30 = (
            db.session.query(func.count(Customers.id))
            .filter(Customers.created_at >= since_30d)
            .scalar()
            or 0
        )
    except Exception:
        new_customers_30 = 0

    # Total appointments (30d)
    total_appts_30 = (
        db.session.query(func.count(Appointment.id))
        .filter(Appointment.start_time >= since_30d)
        .scalar()
        or 0
    )

    # Total salons
    total_salons = db.session.query(func.count(Salon.id)).scalar() or 0

    # Returning users: customers with >=2 appts in last 30 days
    sub = (
        db.session.query(
            Appointment.customer_id.label("cust_id"),
            func.count(Appointment.id).label("num_appts"),
        )
        .filter(Appointment.start_time >= since_30d)
        .group_by(Appointment.customer_id)
        .subquery()
    )

    returning_users_30 = (
        db.session.query(func.count(sub.c.cust_id))
        .filter(sub.c.num_appts >= 2)
        .scalar()
        or 0
    )

    retention_rate = (
        (returning_users_30 / active_users_30 * 100.0)
        if active_users_30 > 0
        else 0.0
    )

    summary_rows = [
        {"Metric": "Active Users (Last 30 Days)", "Value": active_users_30},
        {"Metric": "Total Customers", "Value": total_customers},
        {"Metric": "New Customers (Last 30 Days)", "Value": new_customers_30},
        {"Metric": "Total Appointments (Last 30 Days)", "Value": total_appts_30},
        {"Metric": "Total Salons", "Value": total_salons},
        {"Metric": "Returning Users (Last 30 Days)", "Value": returning_users_30},
        {"Metric": "Retention Rate (Last 30 Days, %)", "Value": round(retention_rate, 2)},
    ]
    summary_df = pd.DataFrame(summary_rows)

    # ---------- APPOINTMENTS SERIES (30d) ----------

    appt_rows = (
        db.session.query(
            func.date(Appointment.start_time).label("day"),
            func.count(Appointment.id).label("appointments"),
        )
        .filter(Appointment.start_time >= since_30d)
        .group_by(func.date(Appointment.start_time))
        .order_by(func.date(Appointment.start_time))
        .all()
    )

    appts_30_series = [
        {"Date": r.day.strftime("%Y-%m-%d"), "Appointments": int(r.appointments)}
        for r in appt_rows
    ]
    appts_df = pd.DataFrame(appts_30_series)

    # ---------- RETURNING USERS SERIES (30d) ----------

    returning_ids = [
        cid
        for (cid,) in db.session.query(sub.c.cust_id)
        .filter(sub.c.num_appts >= 2)
        .all()
    ]

    if returning_ids:
        ret_rows = (
            db.session.query(
                func.date(Appointment.start_time).label("day"),
                func.count(Appointment.id).label("appointments"),
            )
            .filter(Appointment.start_time >= since_30d)
            .filter(Appointment.customer_id.in_(returning_ids))
            .group_by(func.date(Appointment.start_time))
            .order_by(func.date(Appointment.start_time))
            .all()
        )
    else:
        ret_rows = []

    returning_30_series = [
        {"Date": r.day.strftime("%Y-%m-%d"), "ReturningUsers": int(r.appointments)}
        for r in ret_rows
    ]
    returning_df = pd.DataFrame(returning_30_series)

    # ---------- COHORT RETENTION MONTHLY (last ~3 months) ----------

    # Start two months before current month
    first_month = (today.replace(day=1) - timedelta(days=60)).replace(day=1)
    cohort_rows = []

    month_cursor = first_month
    while month_cursor <= today.replace(day=1):
        next_month = (month_cursor + timedelta(days=32)).replace(day=1)

        month_appts = (
            db.session.query(
                Appointment.customer_id.label("cust_id"),
                func.count(Appointment.id).label("num_appts"),
            )
            .filter(
                Appointment.start_time >= month_cursor,
                Appointment.start_time < next_month,
            )
            .group_by(Appointment.customer_id)
            .all()
        )

        active = len(month_appts)
        returning = sum(1 for _, n in month_appts if n >= 2)
        cohort_retention = (returning / active * 100.0) if active > 0 else 0.0

        cohort_rows.append(
            {
                "Month": month_cursor.strftime("%Y-%m"),
                "ActiveUsers": active,
                "ReturningUsers": returning,
                "CohortRetention(%)": round(cohort_retention, 2),
            }
        )

        month_cursor = next_month

    cohort_df = pd.DataFrame(cohort_rows)

    return summary_df, appts_df, returning_df, cohort_df


# -------------------------------------------------------------------
#  SALON ACTIVITY EXPORT
# -------------------------------------------------------------------

def build_salon_activity_export():
    """
    Roughly matches your Salon Activity dashboard:
      - pending salons
      - top salons by bookings (30d)
      - appointments per day per salon (30d)
    """

    since_30d = datetime.utcnow() - timedelta(days=30)

    # Pending verifications based on Salon.status (adjust if you use another field)
    try:
        pending_rows = (
            db.session.query(Salon.id, Salon.name)
            .filter(Salon.status == "PENDING")
            .order_by(Salon.name)
            .all()
        )
        pending_df = pd.DataFrame(
            [{"SalonID": r.id, "SalonName": r.name} for r in pending_rows]
        )
    except Exception:
        pending_df = pd.DataFrame(columns=["SalonID", "SalonName"])

    # Top salons by bookings (30d)
    top_rows = (
        db.session.query(
            Salon.id.label("salon_id"),
            Salon.name.label("salon_name"),
            func.count(Appointment.id).label("bookings"),
        )
        .join(Salon, Appointment.salon_id == Salon.id)
        .filter(Appointment.start_time >= since_30d)
        .group_by(Salon.id, Salon.name)
        .order_by(func.count(Appointment.id).desc())
        .limit(10)
        .all()
    )

    top_df = pd.DataFrame(
        [
            {
                "SalonID": r.salon_id,
                "SalonName": r.salon_name,
                "Bookings(30d)": int(r.bookings),
            }
            for r in top_rows
        ]
    )

    # Appointments per day per salon (30d)
    appt_rows = (
        db.session.query(
            func.date(Appointment.start_time).label("day"),
            Salon.name.label("salon_name"),
            func.count(Appointment.id).label("appointments"),
        )
        .join(Salon, Appointment.salon_id == Salon.id)
        .filter(Appointment.start_time >= since_30d)
        .group_by(func.date(Appointment.start_time), Salon.name)
        .order_by(func.date(Appointment.start_time), Salon.name)
        .all()
    )

    daily_df = pd.DataFrame(
        [
            {
                "Date": r.day.strftime("%Y-%m-%d"),
                "SalonName": r.salon_name,
                "Appointments": int(r.appointments),
            }
            for r in appt_rows
        ]
    )

    return pending_df, top_df, daily_df


# -------------------------------------------------------------------
#  DEMOGRAPHICS & LOYALTY EXPORT
# -------------------------------------------------------------------

def build_demographics_export():
    """
    Exports demographics & loyalty segments. Very defensive:
    if anything about loyalty models/fields fails, we still return
    something instead of crashing.
    """

    # ---------- LOYALTY SUMMARY ----------
    try:
        total_members = (
            db.session.query(func.count(LoyaltyAccount.id)).scalar() or 0
        )

        # Try a few possible balance fields
        balance_expr = None
        for field in ("points", "balance_points", "loyalty_points"):
            if hasattr(LoyaltyAccount, field):
                balance_expr = getattr(LoyaltyAccount, field)
                break

        if balance_expr is not None:
            total_points_balance = (
                db.session.query(func.coalesce(func.sum(balance_expr), 0))
                .scalar()
                or 0
            )
        else:
            total_points_balance = 0

        avg_points_per_member = (
            float(total_points_balance) / float(total_members)
            if total_members > 0
            else 0.0
        )

        active_loyalty_salons = (
            db.session.query(func.count(func.distinct(LoyaltyProgram.salon_id)))
            .filter(LoyaltyProgram.active == 1)
            .scalar()
            or 0
        )

        cutoff_90 = datetime.utcnow() - timedelta(days=90)

        # account id field name
        acct_fk = None
        for field in ("loyalty_account_id", "account_id"):
            if hasattr(LoyaltyTransaction, field):
                acct_fk = getattr(LoyaltyTransaction, field)
                break

        if acct_fk is not None:
            active_members_90 = (
                db.session.query(func.count(func.distinct(acct_fk)))
                .filter(LoyaltyTransaction.created_at >= cutoff_90)
                .scalar()
                or 0
            )
        else:
            active_members_90 = 0

        dormant_members_90 = max(total_members - active_members_90, 0)
        engagement_rate_90 = (
            float(active_members_90) / float(total_members)
            if total_members > 0
            else 0.0
        )

        # points_change field for transactions
        pts_field = None
        for field in ("points_change", "points"):
            if hasattr(LoyaltyTransaction, field):
                pts_field = getattr(LoyaltyTransaction, field)
                break

        if pts_field is not None:
            points_earned_90 = (
                db.session.query(
                    func.coalesce(
                        func.sum(
                            case(
                                (pts_field > 0, pts_field),
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
                                (pts_field < 0, -pts_field),
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
        else:
            points_earned_90 = 0
            points_redeemed_90 = 0

        denom = float(points_earned_90 + points_redeemed_90)
        redemption_rate_90 = float(points_redeemed_90) / denom if denom > 0 else 0.0

        loyalty_summary_df = pd.DataFrame(
            [
                {
                    "TotalMembers": int(total_members),
                    "ActiveLoyaltySalons": int(active_loyalty_salons),
                    "TotalPointsBalance": float(total_points_balance),
                    "AvgPointsPerMember": round(avg_points_per_member, 2),
                    "ActiveMembers(90d)": int(active_members_90),
                    "DormantMembers(90d)": int(dormant_members_90),
                    "EngagementRate(90d%)": round(engagement_rate_90 * 100, 2),
                    "PointsEarned(90d)": float(points_earned_90),
                    "PointsRedeemed(90d)": float(points_redeemed_90),
                    "RedemptionRate(90d%)": round(redemption_rate_90 * 100, 2),
                }
            ]
        )
    except Exception:
        loyalty_summary_df = pd.DataFrame(
            [{"Error": "Loyalty data not available in this environment"}]
        )

    # ---------- APPOINTMENTS BY CITY ----------
    try:
        city_rows = (
            db.session.query(Salon.city, func.count(Appointment.id))
            .join(Salon, Appointment.salon_id == Salon.id)
            .group_by(Salon.city)
            .all()
        )
        appts_city_df = pd.DataFrame(
            [
                {"City": city or "Unknown", "Appointments": int(count)}
                for city, count in city_rows
            ]
        )
    except Exception:
        appts_city_df = pd.DataFrame(columns=["City", "Appointments"])

    # ---------- LOYALTY SEGMENTS ----------
    total_users = db.session.query(func.count(Customers.id)).scalar() or 0
    try:
        # try user_id or customer_id
        acct_user_fk = None
        for field in ("user_id", "customer_id"):
            if hasattr(LoyaltyAccount, field):
                acct_user_fk = getattr(LoyaltyAccount, field)
                break
        if acct_user_fk is not None:
            loyalty_users = (
                db.session.query(func.count(func.distinct(acct_user_fk))).scalar()
                or 0
            )
        else:
            loyalty_users = 0
    except Exception:
        loyalty_users = 0

    guests = max(total_users - loyalty_users, 0)
    segments_df = pd.DataFrame(
        [
            {"Segment": "Loyalty Members", "Count": int(loyalty_users)},
            {"Segment": "Guests", "Count": int(guests)},
        ]
    )

    # ---------- GENDER ----------
    try:
        gender_rows = (
            db.session.query(Customers.gender, func.count(Customers.id))
            .filter(Customers.gender.isnot(None))
            .filter(Customers.gender != "")
            .group_by(Customers.gender)
            .all()
        )
        gender_df = pd.DataFrame(
            [
                {"Gender": gender or "Unknown", "Count": int(count)}
                for gender, count in gender_rows
            ]
        )
    except Exception:
        gender_df = pd.DataFrame(columns=["Gender", "Count"])

    # ---------- AGE GROUPS ----------
    try:
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
            .all()
        )
        age_df = pd.DataFrame(
            [{"AgeGroup": group, "Count": int(count)} for group, count in age_rows]
        )
    except Exception:
        age_df = pd.DataFrame(columns=["AgeGroup", "Count"])

    return loyalty_summary_df, appts_city_df, segments_df, gender_df, age_df


# -------------------------------------------------------------------
#  REVENUE EXPORT
# -------------------------------------------------------------------

def build_revenue_export():
    """
    Revenue & sales export. Uses Order if available; falls back
    to Appointment.total_price if needed.
    """

    since_90d = datetime.utcnow() - timedelta(days=90)

    # ---------- TOTALS & TOP SALON ----------

    # Try using Order table first
    def _order_exists():
        try:
            _ = Order.id  # attribute access to ensure model is imported
            return True
        except Exception:
            return False

    if _order_exists():
        total_revenue = (
            db.session.query(func.coalesce(func.sum(Order.total_amount), 0))
            .filter(Order.created_at >= since_90d)
            .scalar()
            or 0
        )
        total_orders = (
            db.session.query(func.count(Order.id))
            .filter(Order.created_at >= since_90d)
            .scalar()
            or 0
        )
        avg_value = (total_revenue / total_orders) if total_orders > 0 else 0.0

        top_row = (
            db.session.query(
                Salon.name.label("salon_name"),
                func.coalesce(func.sum(Order.total_amount), 0).label("revenue"),
            )
            .join(Salon, Order.salon_id == Salon.id)
            .filter(Order.created_at >= since_90d)
            .group_by(Salon.name)
            .order_by(func.coalesce(func.sum(Order.total_amount), 0).desc())
            .first()
        )
    else:
        # fallback: revenue based on Appointment.total_price
        total_revenue = (
            db.session.query(func.coalesce(func.sum(Appointment.total_price), 0))
            .filter(Appointment.start_time >= since_90d)
            .scalar()
            or 0
        )
        total_orders = (
            db.session.query(func.count(Appointment.id))
            .filter(Appointment.start_time >= since_90d)
            .scalar()
            or 0
        )
        avg_value = (total_revenue / total_orders) if total_orders > 0 else 0.0

        top_row = (
            db.session.query(
                Salon.name.label("salon_name"),
                func.coalesce(func.sum(Appointment.total_price), 0).label("revenue"),
            )
            .join(Salon, Appointment.salon_id == Salon.id)
            .filter(Appointment.start_time >= since_90d)
            .group_by(Salon.name)
            .order_by(func.coalesce(func.sum(Appointment.total_price), 0).desc())
            .first()
        )

    top_salon_name = top_row.salon_name if top_row else ""
    top_salon_revenue = float(top_row.revenue) if top_row else 0.0

    summary_df = pd.DataFrame(
        [
            {
                "TotalRevenue(90d)": float(total_revenue),
                "TotalOrdersOrAppointments(90d)": int(total_orders),
                "AverageTicketValue": round(avg_value, 2),
                "TopSalon": top_salon_name,
                "TopSalonRevenue(90d)": round(top_salon_revenue, 2),
            }
        ]
    )

    # ---------- REVENUE OVER TIME ----------
    if _order_exists():
        rows = (
            db.session.query(
                func.date(Order.created_at).label("day"),
                func.coalesce(func.sum(Order.total_amount), 0).label("revenue"),
            )
            .filter(Order.created_at >= since_90d)
            .group_by(func.date(Order.created_at))
            .order_by(func.date(Order.created_at))
            .all()
        )
    else:
        rows = (
            db.session.query(
                func.date(Appointment.start_time).label("day"),
                func.coalesce(func.sum(Appointment.total_price), 0).label("revenue"),
            )
            .filter(Appointment.start_time >= since_90d)
            .group_by(func.date(Appointment.start_time))
            .order_by(func.date(Appointment.start_time))
            .all()
        )

    revenue_time_df = pd.DataFrame(
        [
            {"Date": r.day.strftime("%Y-%m-%d"), "Revenue": float(r.revenue)}
            for r in rows
        ]
    )

    # ---------- REVENUE BY SALON ----------
    if _order_exists():
        rows = (
            db.session.query(
                Salon.name.label("salon_name"),
                func.coalesce(func.sum(Order.total_amount), 0).label("revenue"),
            )
            .join(Salon, Order.salon_id == Salon.id)
            .filter(Order.created_at >= since_90d)
            .group_by(Salon.name)
            .order_by(func.coalesce(func.sum(Order.total_amount), 0).desc())
            .all()
        )
    else:
        rows = (
            db.session.query(
                Salon.name.label("salon_name"),
                func.coalesce(func.sum(Appointment.total_price), 0).label("revenue"),
            )
            .join(Salon, Appointment.salon_id == Salon.id)
            .filter(Appointment.start_time >= since_90d)
            .group_by(Salon.name)
            .order_by(func.coalesce(func.sum(Appointment.total_price), 0).desc())
            .all()
        )

    revenue_salon_df = pd.DataFrame(
        [
            {"SalonName": r.salon_name, "Revenue(90d)": float(r.revenue)}
            for r in rows
        ]
    )

    return summary_df, revenue_time_df, revenue_salon_df


# -------------------------------------------------------------------
#  MAIN DOWNLOAD ENDPOINT
# -------------------------------------------------------------------

@admin_reports_export_bp.route("/download", methods=["GET"])
def download_reports_excel():
    """
    Multi-section Excel export.
    Frontend passes ?sections=analytics,salon,demographics,revenue
    """

    sections_param = request.args.get(
        "sections", "analytics,salon,demographics,revenue"
    )
    sections = {s.strip().lower() for s in sections_param.split(",") if s.strip()}

    output = io.BytesIO()

    # Use xlsxwriter; if you prefer, omit engine and let pandas choose.
    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        # ---------- ANALYTICS ----------
        if "analytics" in sections:
            summary_df, appts_df, returning_df, cohort_df = build_analytics_export()

            summary_df.to_excel(
                writer, sheet_name="Analytics_Summary", index=False, startrow=0
            )
            appts_df.to_excel(
                writer,
                sheet_name="Analytics_Appointments30d",
                index=False,
                startrow=0,
            )
            returning_df.to_excel(
                writer,
                sheet_name="Analytics_Returning30d",
                index=False,
                startrow=0,
            )
            cohort_df.to_excel(
                writer,
                sheet_name="Analytics_CohortMonthly",
                index=False,
                startrow=0,
            )

        # ---------- SALON ACTIVITY ----------
        if "salon" in sections or "salon_activity" in sections:
            pending_df, top_df, daily_df = build_salon_activity_export()

            pending_df.to_excel(
                writer,
                sheet_name="Salon_Pending",
                index=False,
                startrow=0,
            )
            top_df.to_excel(
                writer,
                sheet_name="Salon_TopBookings30d",
                index=False,
                startrow=0,
            )
            daily_df.to_excel(
                writer,
                sheet_name="Salon_DailyBookings30d",
                index=False,
                startrow=0,
            )

        # ---------- DEMOGRAPHICS & LOYALTY ----------
        if "demographics" in sections:
            (
                loyalty_summary_df,
                appts_city_df,
                segments_df,
                gender_df,
                age_df,
            ) = build_demographics_export()

            loyalty_summary_df.to_excel(
                writer, sheet_name="Demo_LoyaltySummary", index=False, startrow=0
            )
            appts_city_df.to_excel(
                writer,
                sheet_name="Demo_AppointmentsByCity",
                index=False,
                startrow=0,
            )
            segments_df.to_excel(
                writer,
                sheet_name="Demo_Segments",
                index=False,
                startrow=0,
            )
            gender_df.to_excel(
                writer,
                sheet_name="Demo_Gender",
                index=False,
                startrow=0,
            )
            age_df.to_excel(
                writer,
                sheet_name="Demo_AgeGroups",
                index=False,
                startrow=0,
            )

        # ---------- REVENUE ----------
        if "revenue" in sections:
            summary_df, revenue_time_df, revenue_salon_df = build_revenue_export()

            summary_df.to_excel(
                writer,
                sheet_name="Revenue_Summary",
                index=False,
                startrow=0,
            )
            revenue_time_df.to_excel(
                writer,
                sheet_name="Revenue_TimeSeries",
                index=False,
                startrow=0,
            )
            revenue_salon_df.to_excel(
                writer,
                sheet_name="Revenue_BySalon",
                index=False,
                startrow=0,
            )

    output.seek(0)
    filename = f"jade_admin_reports_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.xlsx"

    return send_file(
        output,
        as_attachment=True,
        download_name=filename,
        mimetype=(
            "application/vnd.openxmlformats-officedocument."
            "spreadsheetml.sheet"
        ),
    )
