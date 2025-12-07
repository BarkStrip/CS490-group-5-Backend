from flask import Blueprint, jsonify, request
from datetime import datetime, timedelta
from sqlalchemy import func
from app.extensions import db

# Adjust these imports to your actual model names
from app.models import Order, OrderItem, Salon, Service, Payment, PayMethod

admin_revenue_bp = Blueprint(
    "admin_revenue_bp",
    __name__,
    url_prefix="/api/admin/revenue",
)

# ----------------------------------------------------
# Helpers
# ----------------------------------------------------

def _parse_range():
    """
    range param: "30", "90", or "all" (default: "90")
    Returns (range_param, start_dt, end_dt, from_label, to_label)

    start_dt / end_dt are UTC datetimes for filtering Order.created_at.
    from_label / to_label are date strings for the UI.
    """
    today = datetime.utcnow().date()
    range_param = request.args.get("range", "90")

    if range_param == "30":
        start_date = today - timedelta(days=29)
    elif range_param == "all":
        start_date = None  # all-time
    else:
        # default: 90 days
        start_date = today - timedelta(days=89)

    if start_date is None:
        start_dt = None
        from_label = None
    else:
        start_dt = datetime.combine(start_date, datetime.min.time())
        from_label = start_date.strftime("%Y-%m-%d")

    # upper bound is tomorrow 00:00 (so we include today)
    end_dt = datetime.combine(today + timedelta(days=1), datetime.min.time())
    to_label = today.strftime("%Y-%m-%d")

    return range_param, start_dt, end_dt, from_label, to_label


def _apply_order_filters(query, start_dt, end_dt, salon_id):
    """Apply common filters to an Order-based query: status, date, salon."""
    query = query.filter(Order.status == "completed")

    if start_dt is not None:
        query = query.filter(Order.created_at >= start_dt, Order.created_at < end_dt)

    if salon_id is not None:
        query = query.filter(Order.salon_id == salon_id)

    return query


# ----------------------------------------------------
# 1) SUMMARY: total revenue, orders, AOV, top salon
# ----------------------------------------------------

@admin_revenue_bp.route("/summary", methods=["GET"])
def revenue_summary():
    range_param, start_dt, end_dt, from_label, to_label = _parse_range()

    salon_id_param = request.args.get("salonId")
    salon_id = int(salon_id_param) if salon_id_param and salon_id_param != "all" else None

    # Total revenue + total orders (completed only)
    summary_q = db.session.query(
        func.coalesce(func.sum(Order.total_amnt), 0).label("total_revenue"),
        func.count(Order.id).label("total_orders"),
    )
    summary_q = _apply_order_filters(summary_q, start_dt, end_dt, salon_id)

    total_revenue, total_orders = summary_q.one()
    total_revenue = float(total_revenue or 0)
    total_orders = int(total_orders or 0)
    avg_order_value = round(total_revenue / total_orders, 2) if total_orders > 0 else 0.0

    # Top-grossing salon (within filters)
    top_q = db.session.query(
        Salon.id.label("salon_id"),
        Salon.name.label("salon_name"),
        func.coalesce(func.sum(Order.total_amnt), 0).label("revenue"),
        func.count(Order.id).label("orders"),
    ).join(Salon, Order.salon_id == Salon.id)

    top_q = _apply_order_filters(top_q, start_dt, end_dt, None)  # salon filter only if salon_id is None
    if salon_id is not None:
        top_q = top_q.filter(Order.salon_id == salon_id)

    top_row = top_q.group_by(Salon.id, Salon.name).order_by(
        func.coalesce(func.sum(Order.total_amnt), 0).desc()
    ).first()

    if top_row:
        top_salon = {
            "salonId": top_row.salon_id,
            "salonName": top_row.salon_name,
            "revenue": float(top_row.revenue or 0),
            "orders": int(top_row.orders or 0),
        }
    else:
        top_salon = None

    return jsonify(
        {
            "totalRevenue": round(total_revenue, 2),
            "totalOrders": total_orders,
            "avgOrderValue": avg_order_value,
            "topSalon": top_salon,
            "window": {
                "range": range_param,
                "from": from_label,
                "to": to_label,
            },
        }
    ), 200


# ----------------------------------------------------
# 2) REVENUE TREND (by day)
# ----------------------------------------------------

@admin_revenue_bp.route("/trend", methods=["GET"])
def revenue_trend():
    range_param, start_dt, end_dt, from_label, to_label = _parse_range()

    salon_id_param = request.args.get("salonId")
    salon_id = int(salon_id_param) if salon_id_param and salon_id_param != "all" else None

    # If "all", find earliest completed order to define start_dt
    if range_param == "all":
        earliest = (
            db.session.query(func.min(Order.created_at))
            .filter(Order.status == "completed")
            .scalar()
        )
        if not earliest:
            return jsonify({"trend": []}), 200
        start_dt = datetime.combine(earliest.date(), datetime.min.time())
        from_label = earliest.date().strftime("%Y-%m-%d")
        end_dt = datetime.combine(datetime.utcnow().date() + timedelta(days=1),
                                  datetime.min.time())
        to_label = datetime.utcnow().date().strftime("%Y-%m-%d")

    rows_q = db.session.query(
        func.date(Order.created_at).label("day"),
        func.coalesce(func.sum(Order.total_amnt), 0).label("revenue"),
    )
    rows_q = _apply_order_filters(rows_q, start_dt, end_dt, salon_id)

    rows = (
        rows_q.group_by(func.date(Order.created_at))
        .order_by(func.date(Order.created_at))
        .all()
    )

    revenue_by_day = {r.day: float(r.revenue or 0) for r in rows}

    # Fill missing days with 0
    data = []
    current = start_dt.date()
    last_date = (end_dt - timedelta(seconds=1)).date()

    while current <= last_date:
        data.append(
            {
                "day": current.strftime("%Y-%m-%d"),
                "revenue": revenue_by_day.get(current, 0.0),
            }
        )
        current += timedelta(days=1)

    return jsonify({"trend": data}), 200


# ----------------------------------------------------
# 3) REVENUE BY SALON
# ----------------------------------------------------

@admin_revenue_bp.route("/by-salon", methods=["GET"])
def revenue_by_salon():
    range_param, start_dt, end_dt, _, _ = _parse_range()

    salon_id_param = request.args.get("salonId")
    salon_id = int(salon_id_param) if salon_id_param and salon_id_param != "all" else None

    q = db.session.query(
        Salon.id.label("salon_id"),
        Salon.name.label("salon_name"),
        func.coalesce(func.sum(Order.total_amnt), 0).label("revenue"),
        func.count(Order.id).label("orders"),
    ).join(Salon, Order.salon_id == Salon.id)

    q = _apply_order_filters(q, start_dt, end_dt, salon_id)

    rows = (
        q.group_by(Salon.id, Salon.name)
        .order_by(func.coalesce(func.sum(Order.total_amnt), 0).desc())
        .all()
    )

    data = [
        {
            "salonId": r.salon_id,
            "salonName": r.salon_name,
            "revenue": float(r.revenue or 0),
            "orders": int(r.orders or 0),
        }
        for r in rows
    ]

    return jsonify({"bySalon": data}), 200


# ----------------------------------------------------
# 4) TOP SERVICES BY REVENUE
# ----------------------------------------------------

@admin_revenue_bp.route("/by-service", methods=["GET"])
def revenue_by_service():
    range_param, start_dt, end_dt, _, _ = _parse_range()

    salon_id_param = request.args.get("salonId")
    salon_id = int(salon_id_param) if salon_id_param and salon_id_param != "all" else None

    q = db.session.query(
        Service.id.label("service_id"),
        Service.name.label("service_name"),
        func.coalesce(func.sum(OrderItem.line_total), 0).label("revenue"),
        func.count(OrderItem.id).label("lines"),
    ).join(Order, OrderItem.order_id == Order.id).join(
        Service, OrderItem.service_id == Service.id
    )

    q = _apply_order_filters(q, start_dt, end_dt, salon_id)

    rows = (
        q.group_by(Service.id, Service.name)
        .order_by(func.coalesce(func.sum(OrderItem.line_total), 0).desc())
        .limit(8)
        .all()
    )

    data = [
        {
            "serviceId": r.service_id,
            "serviceName": r.service_name,
            "revenue": float(r.revenue or 0),
            "lines": int(r.lines or 0),
        }
        for r in rows
    ]

    return jsonify({"byService": data}), 200

# ----------------------------------------------------
# 6) SIMPLE SALON LIST FOR DROPDOWN
# ----------------------------------------------------

@admin_revenue_bp.route("/salons", methods=["GET"])
def revenue_salon_list():
    rows = db.session.query(Salon.id, Salon.name).order_by(Salon.name).all()
    return jsonify([{"id": r.id, "name": r.name} for r in rows]), 200
