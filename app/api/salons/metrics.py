from flask import Blueprint, jsonify
from app.extensions import db
from app.models import Order, OrderItem, Salon
from sqlalchemy import func
from datetime import datetime, timedelta

metrics_bp = Blueprint("metrics", __name__, url_prefix="/api/metrics")


@metrics_bp.route("/revenue/<int:salon_id>", methods=["GET"])
def get_revenue_by_month(salon_id):
    """
    Get monthly revenue for a salon over the last 6 months.
    ---
    tags:
      - Metrics
    parameters:
      - name: salon_id
        in: path
        type: integer
        required: true
        description: The salon ID
    responses:
      200:
        description: Monthly revenue data for the last 6 months (most recent first)
        schema:
          type: object
          properties:
            salon_id:
              type: integer
            revenue_by_month:
              type: array
              items:
                type: object
                properties:
                  month:
                    type: string
                    example: "2025-11"
                  total:
                    type: number
                    format: float
      404:
        description: Salon not found
        schema:
          type: object
          properties:
            error:
              type: string
    """
    salon = db.session.get(Salon, salon_id)
    if not salon:
        return jsonify({"error": "Salon not found"}), 404

    # Generate list of last 6 months (most recent first)
    today = datetime.now()
    months = []
    for i in range(6):
        month_date = today - timedelta(days=today.day - 1) - timedelta(days=30 * i)
        months.append((month_date.year, month_date.month))

    # Query revenue data
    revenue_data = (
        db.session.query(
            func.year(Order.created_at).label("year"),
            func.month(Order.created_at).label("month"),
            func.coalesce(func.sum(OrderItem.line_total), 0).label("total"),
        )
        .join(OrderItem, Order.id == OrderItem.order_id)
        .filter(Order.salon_id == salon_id)
        .group_by(
            func.year(Order.created_at),
            func.month(Order.created_at),
        )
        .all()
    )

    # Build month -> total map
    revenue_map = {(row.year, row.month): float(row.total) for row in revenue_data}

    # Build response with all 6 months (sorted most recent first)
    revenue_by_month = []
    for year, month in months:
        month_str = f"{year:04d}-{month:02d}"
        total = revenue_map.get((year, month), 0.0)
        revenue_by_month.append({"month": month_str, "total": total})

    return jsonify(
        {
            "salon_id": salon_id,
            "revenue_by_month": revenue_by_month,
        }
    )
