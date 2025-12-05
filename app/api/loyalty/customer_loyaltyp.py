# loyalty.py
from flask import Blueprint, jsonify, request, current_app
from sqlalchemy import select, func
from app.extensions import db
from ...models import (
    Customers,
    Salon,
    LoyaltyAccount,
    LoyaltyProgram,
    Appointment,
    LoyaltyTransaction,
    Promos,
)
from datetime import datetime, timedelta
from decimal import Decimal
import uuid
import math

loyalty_bp = Blueprint("loyalty", __name__, url_prefix="/api/loyalty")


def get_customer_from_id(customer_id):
    """Helper to find a customer by their main ID (not auth_user.id)."""
    return db.session.get(Customers, customer_id)


def get_loyalty_account(customer_id, salon_id):
    """Helper to get a specific loyalty account."""
    return db.session.scalars(
        select(LoyaltyAccount)
        .where(LoyaltyAccount.user_id == customer_id)
        .where(LoyaltyAccount.salon_id == salon_id)
    ).first()


@loyalty_bp.route("/customers/<int:customer_id>/dashboard", methods=["GET"])
def get_loyalty_dashboard(customer_id):
    try:
        customer = get_customer_from_id(customer_id)
        if not customer:
            return jsonify({"status": "error", "message": "Customer not found"}), 404

        accounts = db.session.scalars(
            select(LoyaltyAccount).where(LoyaltyAccount.user_id == customer_id)
        ).all()

        active_programs_count = len(accounts)
        current_total_points = sum(acc.points for acc in accounts)

        total_visits = db.session.scalar(
            select(func.count(Appointment.id))
            .where(Appointment.customer_id == customer_id)
            .where(Appointment.status == "COMPLETED")
        )

        response = {
            "current_total_points": current_total_points,
            "active_programs_count": active_programs_count,
            "total_visits_all_time": total_visits or 0,
        }
        return jsonify(response)

    except Exception as e:
        current_app.logger.error(
            f"Failed to get loyalty dashboard for customer {customer_id}: {e}"
        )
        return jsonify({"status": "error", "message": "Failed to get dashboard", "details": str(e)}), 500


@loyalty_bp.route("/customers/<int:customer_id>/programs", methods=["GET"])
def get_customer_loyalty_programs(customer_id):
    try:
        customer = get_customer_from_id(customer_id)
        if not customer:
            return jsonify({"status": "error", "message": "Customer not found"}), 404

        stmt = (
            select(LoyaltyAccount, Salon, LoyaltyProgram)
            .join(Salon, LoyaltyAccount.salon_id == Salon.id)
            .join(LoyaltyProgram, LoyaltyProgram.salon_id == Salon.id)
            .where(LoyaltyAccount.user_id == customer_id)
            .where(LoyaltyProgram.active == 1)
        )

        results = db.session.execute(stmt).all()

        response_list = []
        for acc, salon, program in results:
            visits_at_salon = db.session.scalar(
                select(func.count(Appointment.id))
                .where(Appointment.customer_id == customer_id)
                .where(Appointment.salon_id == salon.id)
                .where(Appointment.status == "COMPLETED")
            )

            points_for_reward = getattr(program, "points_for_reward", None)
            if points_for_reward is None:
                points_for_reward = 1000

            raw_ppd = getattr(program, "points_per_dollar", None)
            if raw_ppd is None:
                ppd_value = 1.0
            else:
                ppd_value = float(raw_ppd)

            response_list.append(
                {
                    "salon_id": salon.id,
                    "salon_name": salon.name,
                    "current_points": acc.points,
                    "total_visits_at_salon": visits_at_salon or 0,
                    "program_details": {
                        "description": getattr(
                            program, "reward_description", f"{points_for_reward} points for reward"
                        ),
                        "points_per_dollar": ppd_value,
                    },
                    "next_reward_progress": {
                        "points_to_next_reward": points_for_reward,
                        "points_away": max(0, points_for_reward - acc.points),
                    },
                }
            )

        return jsonify(response_list)

    except Exception as e:
        current_app.logger.error(
            f"Failed to get loyalty programs for customer {customer_id}: {e}"
        )
        return jsonify({"status": "error", "message": "Failed to get programs", "details": str(e)}), 500


@loyalty_bp.route("/customers/<int:customer_id>/programs/<int:salon_id>/activity", methods=["GET"])
def get_loyalty_activity(customer_id, salon_id):
    try:
        account = get_loyalty_account(customer_id, salon_id)
        if not account:
            return jsonify({"status": "error", "message": "Loyalty account not found for this customer and salon"}), 404

        stmt = (
            select(LoyaltyTransaction)
            .where(LoyaltyTransaction.loyalty_account_id == account.id)
            .order_by(LoyaltyTransaction.created_at.desc())
            .limit(20)
        )
        transactions = db.session.scalars(stmt).all()

        activity_list = []
        for txn in transactions:
            activity_list.append(
                {
                    "activity_id": f"txn_{txn.id}",
                    "date": txn.created_at.isoformat(),
                    "description": txn.reason,
                    "points_change": txn.points_change,
                }
            )

        return jsonify(activity_list)
    except Exception as e:
        current_app.logger.error(f"Failed to get loyalty activity for cust {customer_id}, salon {salon_id}: {e}")
        return jsonify({"status": "error", "message": "Failed to get activity", "details": str(e)}), 500


@loyalty_bp.route("/customers/<int:customer_id>/programs/<int:salon_id>/rewards", methods=["GET"])
def get_available_rewards(customer_id, salon_id):
    try:
        account = get_loyalty_account(customer_id, salon_id)
        if not account:
            return jsonify({"status": "error", "message": "Loyalty account not found"}), 404

        program = db.session.scalar(
            select(LoyaltyProgram).where(LoyaltyProgram.salon_id == salon_id)
        )
        if not program or not program.active:
            return jsonify({"status": "error", "message": "No active loyalty program for this salon"}), 404

        points_for_reward = getattr(program, "points_for_reward", None)
        if points_for_reward is None:
            points_for_reward = 1000

        can_redeem = account.points >= points_for_reward
        rv = program.reward_value
        reward_value = float(rv) if rv is not None else 0.0

        reward_list = [
            {
                "reward_id": f"prog_{program.id}_main_reward",
                "description": getattr(program, "reward_description", f"{reward_value}% off"),
                "points_cost": points_for_reward,
                "is_redeemable": can_redeem,
                "reward_type": str(program.reward_type),
                "reward_value": reward_value,
            }
        ]

        return jsonify(reward_list)
    except Exception as e:
        current_app.logger.error(f"Failed to get available rewards for cust {customer_id}, salon {salon_id}: {e}")
        return jsonify({"status": "error", "message": "Failed to get rewards", "details": str(e)}), 500


@loyalty_bp.route("/customers/<int:customer_id>/programs/<int:salon_id>/redeem", methods=["POST"])
def redeem_loyalty_reward(customer_id, salon_id):
    try:
        data = request.json or {}
        reward_id = data.get("reward_id")
        if not reward_id:
            return jsonify({"status": "error", "message": "reward_id is required"}), 400

        account = get_loyalty_account(customer_id, salon_id)
        if not account:
            return jsonify({"status": "error", "message": "Loyalty account not found"}), 404

        program = db.session.scalar(
            select(LoyaltyProgram).where(LoyaltyProgram.salon_id == salon_id)
        )
        if not program:
            return jsonify({"status": "error", "message": "Loyalty program not found"}), 404

        points_for_reward = getattr(program, "points_for_reward", None)
        if points_for_reward is None:
            points_for_reward = 1000

        points_cost = points_for_reward
        if account.points < points_cost:
            return jsonify({"status": "error", "message": "Not enough points"}), 400

        account.points -= points_cost
        db.session.add(account)

        new_txn = LoyaltyTransaction(
            loyalty_account_id=account.id,
            points_change=-points_cost,
            reason="REDEEM_REWARD",
        )
        db.session.add(new_txn)

        promo_code = f"LOYALTY-{str(uuid.uuid4())[:8].upper()}"
        expires = datetime.utcnow() + timedelta(days=30)

        new_promo = Promos(
            code=promo_code,
            type=program.reward_type,
            value=program.reward_value,
            is_active=True,
            expires_at=expires,
            description=f"Loyalty Reward for Customer {customer_id} from Salon {salon_id}",
        )
        db.session.add(new_promo)

        db.session.commit()

        return jsonify({
            "status": "success",
            "message": "Reward redeemed successfully!",
            "data": {
                "new_points_balance": account.points,
                "promo_code_generated": new_promo.code,
                "expires_at": new_promo.expires_at.isoformat(),
            },
        }), 201

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Failed to redeem reward for cust {customer_id}, salon {salon_id}: {e}")
        return jsonify({"status": "error", "message": "Failed to redeem reward", "details": str(e)}), 500


@loyalty_bp.route("/salon/<int:salon_id>", methods=["GET"])
def get_salon_loyalty_program(salon_id):
    try:
        salon = db.session.get(Salon, salon_id)
        if not salon:
            return jsonify({"error": "Salon not found", "message": f"No salon found with ID {salon_id}"}), 404

        loyalty_program = db.session.query(LoyaltyProgram).filter(LoyaltyProgram.salon_id == salon_id).first()

        if not loyalty_program:
            return jsonify({
                "status": "success",
                "salon_id": salon_id,
                "id": None,
                "active": None,
                "points_per_dollar": None,
                "points_for_reward": None,
                "visits_for_reward": None,
                "reward_type": None,
                "reward_value": None,
                "reward_description": None,
                "created_at": None,
                "updated_at": None,
            }), 200

        return jsonify({
            "status": "success",
            "salon_id": salon_id,
            "id": loyalty_program.id,
            "active": loyalty_program.active,
            "points_per_dollar": float(loyalty_program.points_per_dollar) if loyalty_program.points_per_dollar is not None else None,
            "points_for_reward": loyalty_program.points_for_reward,
            "visits_for_reward": loyalty_program.visits_for_reward,
            "reward_type": loyalty_program.reward_type,
            "reward_value": str(loyalty_program.reward_value) if loyalty_program.reward_value else None,
            "reward_description": loyalty_program.reward_description,
            "created_at": loyalty_program.created_at.isoformat() if loyalty_program.created_at else None,
            "updated_at": loyalty_program.updated_at.isoformat() if loyalty_program.updated_at else None,
        }), 200
    except Exception as e:
        return jsonify({"error": "Database error", "details": str(e)}), 500


@loyalty_bp.route("/salon/<int:salon_id>", methods=["PUT"])
def update_salon_loyalty_program(salon_id):
    try:
        salon = db.session.get(Salon, salon_id)
        if not salon:
            return jsonify({"error": "Salon not found", "message": f"No salon found with ID {salon_id}"}), 404

        data = request.get_json()
        if not data:
            return jsonify({"error": "Request body required", "message": "JSON body with fields to update is required"}), 400

        loyalty_program = db.session.query(LoyaltyProgram).filter(LoyaltyProgram.salon_id == salon_id).first()
        if not loyalty_program:
            loyalty_program = LoyaltyProgram(salon_id=salon_id)
            db.session.add(loyalty_program)

        if "active" in data:
            active = data.get("active")
            if active not in [0, 1]:
                return jsonify({"error": "Invalid value", "message": "active must be 0 or 1"}), 400
            loyalty_program.active = active

        if "points_per_dollar" in data:
            ppd = data.get("points_per_dollar")
            try:
                if ppd is None or ppd == "":
                    loyalty_program.points_per_dollar = None
                else:
                    loyalty_program.points_per_dollar = Decimal(str(ppd))
            except Exception:
                return jsonify({"error": "Invalid value", "message": "points_per_dollar must be a valid decimal number"}), 400

        if "points_for_reward" in data:
            pfr = data.get("points_for_reward")
            if pfr is not None:
                try:
                    pfr_int = int(pfr)
                except (TypeError, ValueError):
                    return jsonify({"error": "Invalid value", "message": "points_for_reward must be an integer"}), 400
                if pfr_int < 0:
                    return jsonify({"error": "Invalid value", "message": "points_for_reward must be non-negative"}), 400
                loyalty_program.points_for_reward = pfr_int

        if "visits_for_reward" in data:
            visits = data.get("visits_for_reward")
            if not isinstance(visits, int) or visits < 0:
                return jsonify({"error": "Invalid value", "message": "visits_for_reward must be a non-negative integer"}), 400
            loyalty_program.visits_for_reward = visits

        if "reward_type" in data:
            reward_type = data.get("reward_type")
            if reward_type not in ["PERCENT", "FIXED_AMOUNT", "FREE_ITEM"]:
                return jsonify({"error": "Invalid value", "message": "reward_type must be 'PERCENT', 'FIXED_AMOUNT', or 'FREE_ITEM'"}), 400
            loyalty_program.reward_type = reward_type

        if "reward_value" in data:
            reward_value = data.get("reward_value")
            try:
                loyalty_program.reward_value = None if reward_value is None or reward_value == "" else Decimal(str(reward_value))
            except Exception:
                return jsonify({"error": "Invalid value", "message": "reward_value must be a valid decimal number"}), 400

        if "reward_description" in data:
            reward_description = data.get("reward_description")
            if reward_description and len(str(reward_description)) > 255:
                return jsonify({"error": "Invalid value", "message": "reward_description cannot exceed 255 characters"}), 400
            loyalty_program.reward_description = reward_description

        db.session.commit()

        return jsonify({
            "status": "success",
            "message": "Loyalty program updated successfully",
            "salon_id": salon_id,
            "id": loyalty_program.id,
            "active": loyalty_program.active,
            "points_per_dollar": float(loyalty_program.points_per_dollar) if loyalty_program.points_per_dollar is not None else None,
            "points_for_reward": loyalty_program.points_for_reward,
            "visits_for_reward": loyalty_program.visits_for_reward,
            "reward_type": loyalty_program.reward_type,
            "reward_value": str(loyalty_program.reward_value) if loyalty_program.reward_value else None,
            "reward_description": loyalty_program.reward_description,
            "created_at": loyalty_program.created_at.isoformat() if loyalty_program.created_at else None,
            "updated_at": loyalty_program.updated_at.isoformat() if loyalty_program.updated_at else None,
        }), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": "Database error", "details": str(e)}), 500


@loyalty_bp.route("/cart/check-rewards", methods=["POST"])
def check_cart_rewards():
    """
    Backwards-compatible endpoint — returns similar structure as before.
    Input: { "customer_id": 123, "salon_ids": [1, 2, 5] }
    """
    data = request.get_json()
    customer_id = data.get("customer_id")
    salon_ids = data.get("salon_ids", [])

    response = {}

    for salon_id in salon_ids:
        program: LoyaltyProgram = LoyaltyProgram.query.filter_by(
            salon_id=salon_id, active=1, program_type="POINTS"
        ).first()

        if not program:
            response[str(salon_id)] = {"info_text": "No points available for use", "max_discount": 0}
            continue

        account: LoyaltyAccount = LoyaltyAccount.query.filter_by(user_id=customer_id, salon_id=salon_id).first()

        if not account or account.points <= 0:
            response[str(salon_id)] = {"info_text": "No points available for use", "max_discount": 0}
            continue

        total_points = account.points
        points_required = program.points_for_reward or 1000
        reward_value = float(program.reward_value or 0)

        reward_chunks = total_points // points_required
        eligible_discount = round(float(reward_chunks * reward_value), 0)

        formatted_discount = f"{eligible_discount:.2f}"

        if eligible_discount <= 0:
            response[str(salon_id)] = {"info_text": "No points available for use", "max_discount": 0}
            continue

        response[str(salon_id)] = {
            "total_points": total_points,
            "eligible_discount": eligible_discount,
            "info_text": f"{total_points} total points. Eligible for ${formatted_discount} off",
            "max_discount": eligible_discount
        }

    return jsonify(response)


@loyalty_bp.route("/cart/checkout-preview", methods=["POST"])
def checkout_preview():
    """
    Checkout preview endpoint — returns loyalty info ONLY for salons
    the user is currently purchasing from.
    """

    data = request.get_json() or {}
    customer_id = data.get("customer_id")
    cart_spending = data.get("cart_spending", [])

    if customer_id is None:
        return jsonify({"error": "customer_id required"}), 400

    # Build mapping: { salon_id: amount_spent }
    spend_by_salon = {}
    for entry in cart_spending:
        try:
            sid = int(entry.get("salon_id"))
        except Exception:
            continue
        amt = float(entry.get("amount_spent", 0) or 0)
        spend_by_salon[sid] = spend_by_salon.get(sid, 0) + amt

    # IMPORTANT: Only use salons user is buying from
    salon_ids = list(spend_by_salon.keys())
    response = {}

    try:
        for salon_id in salon_ids:

            salon = db.session.get(Salon, salon_id)
            salon_name = salon.name if salon else f"Salon #{salon_id}"

            program: LoyaltyProgram = db.session.scalar(
                select(LoyaltyProgram)
                .where(LoyaltyProgram.salon_id == salon_id)
            )

            account: LoyaltyAccount = db.session.scalar(
                select(LoyaltyAccount)
                .where(LoyaltyAccount.user_id == customer_id)
                .where(LoyaltyAccount.salon_id == salon_id)
            )

            current_points = account.points if account else 0

            # No program, inactive, or not points-based
            if not program or not program.active or program.program_type != "POINTS":
                estimated_points = int(
                    spend_by_salon.get(salon_id, 0) *
                    (float(program.points_per_dollar) if program else 0)
                )

                response[str(salon_id)] = {
                    "salon_id": salon_id,
                    "salon_name": salon_name,
                    "total_points": current_points,
                    "eligible_discount": 0,
                    "info_text": "No points available for use",
                    "max_discount": 0,
                    "estimated_points_earned": estimated_points
                }
                continue

            # Program details
            points_for_reward = int(program.points_for_reward or 1000)
            reward_value = float(program.reward_value or 0.0)
            ppd = int(program.points_per_dollar or 1)

            # Eligible discount from existing points
            reward_chunks = current_points // points_for_reward
            eligible_discount = round(reward_chunks * reward_value, 2)

            # Amount spent now
            amount_spent = float(spend_by_salon.get(salon_id, 0))
            estimated_points = int(math.floor(amount_spent * ppd))

            # Build info_text
            if current_points == 0:
                # No points yet
                info_text = (
                    f"No points yet — you'll earn {estimated_points} points from this purchase"
                )
                max_discount = 0

            elif current_points < points_for_reward:
                # Have some points but not enough
                points_needed = points_for_reward - current_points

                info_text = (
                    f"Total points: {current_points} — you'll earn {estimated_points} points from this purchase. "
                    f"{points_needed} points away from a ${reward_value:.0f} discount"
                )
                max_discount = 0

            else:
                # Eligible for reward
                info_text = (
                    f"{current_points} total points. Eligible for ${eligible_discount:.2f} off"
                )
                max_discount = eligible_discount

            # Build response for this salon
            response[str(salon_id)] = {
                "salon_id": salon_id,
                "salon_name": salon_name,
                "total_points": current_points,
                "eligible_discount": eligible_discount,
                "info_text": info_text,
                "max_discount": max_discount,
                "estimated_points_earned": estimated_points
            }

        return jsonify(response)

    except Exception as e:
        current_app.logger.error(f"checkout-preview failed: {e}")
        return jsonify({
            "status": "error",
            "message": "checkout preview failed",
            "details": str(e)
        }), 500


@loyalty_bp.route("/apply-earned-points", methods=["POST"])
def apply_earned_points():
    data = request.get_json()
    customer_id = data.get("customer_id")
    spending = data.get("spending", [])

    for entry in spending:
        salon_id = entry["salon_id"]
        amount_spent = float(entry["amount_spent"])

        program: LoyaltyProgram = LoyaltyProgram.query.filter_by(
            salon_id=salon_id, active=1, program_type="POINTS"
        ).first()

        if not program:
            continue

        earned_points = int(math.floor(amount_spent * float(program.points_per_dollar or 0)))

        account = LoyaltyAccount.query.filter_by(user_id=customer_id, salon_id=salon_id).first()

        if account:
            account.points += earned_points
        else:
            account = LoyaltyAccount(user_id=customer_id, salon_id=salon_id, points=earned_points)
            db.session.add(account)

    db.session.commit()
    return jsonify({"success": True})
