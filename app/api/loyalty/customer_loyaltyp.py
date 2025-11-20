# Points, promotions, redemption
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
import uuid

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
    """
    Get customer loyalty dashboard summary
    ---
    summary: Returns aggregated loyalty stats for the customer
    description: Powers the top-level summary cards in your UI (e.g., "Lifetime Points", "Active Programs", "Total Visits").
    parameters:
      - name: customer_id
        in: path
        type: integer
        required: true
        description: The ID of the customer
    responses:
      200:
        description: Returns total points, active programs count, and visit count.
      404:
        description: Customer not found
      500:
        description: Server error
    """
    try:
        customer = get_customer_from_id(customer_id)
        if not customer:
            return jsonify({"status": "error", "message": "Customer not found"}), 404

        # 1. Get all loyalty accounts for this customer
        accounts = db.session.scalars(
            select(LoyaltyAccount).where(LoyaltyAccount.user_id == customer_id)
        ).all()

        # 2. Calculate stats
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
        return (
            jsonify(
                {
                    "status": "error",
                    "message": "Failed to get dashboard",
                    "details": str(e),
                }
            ),
            500,
        )


@loyalty_bp.route("/customers/<int:customer_id>/programs", methods=["GET"])
def get_customer_loyalty_programs(customer_id):
    """
    Get all loyalty programs for a customer
    ---
    summary: Returns all active loyalty programs for a given customer
    description: Powers the main list in your UI (e.g., the "Jade Boutique" card).
    parameters:
      - name: customer_id
        in: path
        type: integer
        required: true
        description: The ID of the customer
    responses:
      200:
        description: Returns a list of loyalty programs for the customer
      404:
        description: Customer not found
      500:
        description: Server error
    """
    try:
        customer = get_customer_from_id(customer_id)
        if not customer:
            return jsonify({"status": "error", "message": "Customer not found"}), 404

        stmt = (
            select(LoyaltyAccount, Salon, LoyaltyProgram)
            .join(Salon, LoyaltyAccount.salon_id == Salon.id)
            .join(LoyaltyProgram, LoyaltyProgram.salon_id == Salon.id)
            .where(LoyaltyAccount.user_id == customer_id)
            .where(LoyaltyProgram.active is True)
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

            points_for_reward = getattr(program, "points_for_reward", 1000)
            points_away = max(0, points_for_reward - acc.points)

            response_list.append(
                {
                    "salon_id": salon.id,
                    "salon_name": salon.name,
                    "current_points": acc.points,
                    "total_visits_at_salon": visits_at_salon or 0,
                    "program_details": {
                        "description": getattr(
                            program,
                            "reward_description",
                            f"{points_for_reward} points for reward",
                        ),
                        "points_per_dollar": float(
                            getattr(program, "points_per_dollar", 1)
                        ),
                    },
                    "next_reward_progress": {
                        "points_to_next_reward": points_for_reward,
                        "points_away": points_away,
                    },
                }
            )

        return jsonify(response_list)

    except Exception as e:
        current_app.logger.error(
            f"Failed to get loyalty programs for customer {customer_id}: {e}"
        )
        return (
            jsonify(
                {
                    "status": "error",
                    "message": "Failed to get programs",
                    "details": str(e),
                }
            ),
            500,
        )


@loyalty_bp.route(
    "/customers/<int:customer_id>/programs/<int:salon_id>/activity", methods=["GET"]
)
def get_loyalty_activity(customer_id, salon_id):
    """
    Get recent loyalty activity for a customer at a specific salon
    ---
    summary: Returns loyalty transaction history
    description: Retrieves the most recent 20 loyalty transactions for a customer and salon.
    parameters:
      - name: customer_id
        in: path
        type: integer
        required: true
        description: The ID of the customer
      - name: salon_id
        in: path
        type: integer
        required: true
        description: The ID of the salon
    responses:
      200:
        description: List of recent loyalty transactions
      404:
        description: Loyalty account not found
      500:
        description: Server error
    """
    try:
        account = get_loyalty_account(customer_id, salon_id)
        if not account:
            return (
                jsonify(
                    {
                        "status": "error",
                        "message": "Loyalty account not found for this customer and salon",
                    }
                ),
                404,
            )

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
        current_app.logger.error(
            f"Failed to get loyalty activity for cust {customer_id}, salon {salon_id}: {e}"
        )
        return (
            jsonify(
                {
                    "status": "error",
                    "message": "Failed to get activity",
                    "details": str(e),
                }
            ),
            500,
        )


@loyalty_bp.route(
    "/customers/<int:customer_id>/programs/<int:salon_id>/rewards", methods=["GET"]
)
def get_available_rewards(customer_id, salon_id):
    """
    Get available loyalty rewards
    ---
    summary: Returns rewards a customer can redeem using points
    description: Fetches loyalty rewards available for the customer's active salon program.
    parameters:
      - name: customer_id
        in: path
        type: integer
        required: true
      - name: salon_id
        in: path
        type: integer
        required: true
    responses:
      200:
        description: List of redeemable rewards
      404:
        description: Loyalty account or program not found
      500:
        description: Server error
    """
    try:
        account = get_loyalty_account(customer_id, salon_id)
        if not account:
            return (
                jsonify({"status": "error", "message": "Loyalty account not found"}),
                404,
            )

        program = db.session.scalar(
            select(LoyaltyProgram).where(LoyaltyProgram.salon_id == salon_id)
        )
        if not program or not program.active:
            return (
                jsonify(
                    {
                        "status": "error",
                        "message": "No active loyalty program for this salon",
                    }
                ),
                404,
            )

        points_for_reward = getattr(program, "points_for_reward", 1000)
        can_redeem = account.points >= points_for_reward

        reward_list = [
            {
                "reward_id": f"prog_{program.id}_main_reward",
                "description": getattr(
                    program, "reward_description", f"{program.reward_value}% off"
                ),
                "points_cost": points_for_reward,
                "is_redeemable": can_redeem,
                "reward_type": str(program.reward_type),
                "reward_value": float(program.reward_value),
            }
        ]

        return jsonify(reward_list)

    except Exception as e:
        current_app.logger.error(
            f"Failed to get available rewards for cust {customer_id}, salon {salon_id}: {e}"
        )
        return (
            jsonify(
                {
                    "status": "error",
                    "message": "Failed to get rewards",
                    "details": str(e),
                }
            ),
            500,
        )


@loyalty_bp.route(
    "/customers/<int:customer_id>/programs/<int:salon_id>/redeem", methods=["POST"]
)
def redeem_loyalty_reward(customer_id, salon_id):
    """
    Redeem a loyalty reward
    ---
    summary: Spend points to redeem a reward
    description: Deducts points, logs the transaction, and generates a one-time promo code for the customer.
    parameters:
      - name: customer_id
        in: path
        type: integer
        required: true
      - name: salon_id
        in: path
        type: integer
        required: true
      - name: body
        in: body
        required: true
        schema:
          type: object
          properties:
            reward_id:
              type: string
              example: "prog_123_main_reward"
    responses:
      201:
        description: Reward redeemed successfully
      400:
        description: Not enough points or invalid data
      404:
        description: Loyalty account or program not found
      500:
        description: Server error
    """
    try:
        data = request.json
        reward_id = data.get("reward_id")
        if not reward_id:
            return jsonify({"status": "error", "message": "reward_id is required"}), 400

        account = get_loyalty_account(customer_id, salon_id)
        if not account:
            return (
                jsonify({"status": "error", "message": "Loyalty account not found"}),
                404,
            )

        program = db.session.scalar(
            select(LoyaltyProgram).where(LoyaltyProgram.salon_id == salon_id)
        )
        if not program:
            return (
                jsonify({"status": "error", "message": "Loyalty program not found"}),
                404,
            )

        points_cost = getattr(program, "points_for_reward", 1000)

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

        return (
            jsonify(
                {
                    "status": "success",
                    "message": "Reward redeemed successfully!",
                    "data": {
                        "new_points_balance": account.points,
                        "promo_code_generated": new_promo.code,
                        "expires_at": new_promo.expires_at.isoformat(),
                    },
                }
            ),
            201,
        )

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(
            f"Failed to redeem reward for cust {customer_id}, salon {salon_id}: {e}"
        )
        return (
            jsonify(
                {
                    "status": "error",
                    "message": "Failed to redeem reward",
                    "details": str(e),
                }
            ),
            500,
        )


@loyalty_bp.route("/salon/<int:salon_id>", methods=["GET"])
def get_salon_loyalty_program(salon_id):
    """
    GET /api/loyalty/salon/<salon_id>
    Purpose: Retrieve loyalty program details for a specific salon.
    Input: salon_id (integer) from the URL path.
    Behavior:
    - Check if salon exists
    - Retrieve loyalty program details if it exists
    - Return flattened loyalty program data with 200 status
    - Return None if no loyalty program exists for salon
    """
    try:
        # Verify salon exists
        salon = db.session.get(Salon, salon_id)
        if not salon:
            return (
                jsonify(
                    {
                        "error": "Salon not found",
                        "message": f"No salon found with ID {salon_id}",
                    }
                ),
                404,
            )

        # Get loyalty program for this salon
        loyalty_program = (
            db.session.query(LoyaltyProgram)
            .filter(LoyaltyProgram.salon_id == salon_id)
            .first()
        )

        if not loyalty_program:
            return (
                jsonify(
                    {
                        "status": "success",
                        "salon_id": salon_id,
                        "id": None,
                        "active": None,
                        "visits_for_reward": None,
                        "reward_type": None,
                        "reward_value": None,
                        "reward_description": None,
                        "created_at": None,
                        "updated_at": None,
                    }
                ),
                200,
            )

        # Return flattened loyalty program details (no nested object)
        return (
            jsonify(
                {
                    "status": "success",
                    "salon_id": salon_id,
                    "id": loyalty_program.id,
                    "active": loyalty_program.active,
                    "visits_for_reward": loyalty_program.visits_for_reward,
                    "reward_type": loyalty_program.reward_type,
                    "reward_value": (
                        str(loyalty_program.reward_value)
                        if loyalty_program.reward_value
                        else None
                    ),
                    "reward_description": loyalty_program.reward_description,
                    "created_at": (
                        loyalty_program.created_at.isoformat()
                        if loyalty_program.created_at
                        else None
                    ),
                    "updated_at": (
                        loyalty_program.updated_at.isoformat()
                        if loyalty_program.updated_at
                        else None
                    ),
                }
            ),
            200,
        )

    except Exception as e:
        return jsonify({"error": "Database error", "details": str(e)}), 500


@loyalty_bp.route("/salon/<int:salon_id>", methods=["PUT"])
def update_salon_loyalty_program(salon_id):
    """
    PUT /api/loyalty/salon/<salon_id>
    Purpose: Update loyalty program details for a specific salon.
    Input:
        - salon_id (integer) from the URL path
        - JSON body with fields to update:
          * active (optional, 0 or 1)
          * visits_for_reward (optional, integer)
          * reward_type (optional, 'PERCENT', 'FIXED_AMOUNT', or 'FREE_ITEM')
          * reward_value (optional, decimal)
          * reward_description (optional, string)
    Behavior:
    - Check if salon exists
    - Retrieve loyalty program for salon
    - If no loyalty program exists, create a new one
    - Update provided fields
    - Return updated loyalty program data
    """
    try:
        # Verify salon exists
        salon = db.session.get(Salon, salon_id)
        if not salon:
            return (
                jsonify(
                    {
                        "error": "Salon not found",
                        "message": f"No salon found with ID {salon_id}",
                    }
                ),
                404,
            )

        # Get request body
        data = request.get_json()
        if not data:
            return (
                jsonify(
                    {
                        "error": "Request body required",
                        "message": "JSON body with fields to update is required",
                    }
                ),
                400,
            )

        # Get or create loyalty program
        loyalty_program = (
            db.session.query(LoyaltyProgram)
            .filter(LoyaltyProgram.salon_id == salon_id)
            .first()
        )

        if not loyalty_program:
            # Create new loyalty program
            loyalty_program = LoyaltyProgram(salon_id=salon_id)
            db.session.add(loyalty_program)

        # Update fields if provided
        if "active" in data:
            active = data.get("active")
            if active not in [0, 1]:
                return (
                    jsonify(
                        {"error": "Invalid value", "message": "active must be 0 or 1"}
                    ),
                    400,
                )
            loyalty_program.active = active

        if "visits_for_reward" in data:
            visits = data.get("visits_for_reward")
            if not isinstance(visits, int) or visits < 0:
                return (
                    jsonify(
                        {
                            "error": "Invalid value",
                            "message": "visits_for_reward must be a non-negative integer",
                        }
                    ),
                    400,
                )
            loyalty_program.visits_for_reward = visits

        if "reward_type" in data:
            reward_type = data.get("reward_type")
            if reward_type not in ["PERCENT", "FIXED_AMOUNT", "FREE_ITEM"]:
                return (
                    jsonify(
                        {
                            "error": "Invalid value",
                            "message": "reward_type must be 'PERCENT', 'FIXED_AMOUNT', or 'FREE_ITEM'",
                        }
                    ),
                    400,
                )
            loyalty_program.reward_type = reward_type

        if "reward_value" in data:
            reward_value = data.get("reward_value")
            try:
                # Convert to Decimal for validation
                from decimal import Decimal

                loyalty_program.reward_value = Decimal(str(reward_value))
            except Exception:
                return (
                    jsonify(
                        {
                            "error": "Invalid value",
                            "message": "reward_value must be a valid decimal number",
                        }
                    ),
                    400,
                )

        if "reward_description" in data:
            reward_description = data.get("reward_description")
            if reward_description and len(str(reward_description)) > 255:
                return (
                    jsonify(
                        {
                            "error": "Invalid value",
                            "message": "reward_description cannot exceed 255 characters",
                        }
                    ),
                    400,
                )
            loyalty_program.reward_description = reward_description

        # Commit changes
        db.session.commit()

        # Return updated loyalty program
        return (
            jsonify(
                {
                    "status": "success",
                    "message": "Loyalty program updated successfully",
                    "salon_id": salon_id,
                    "id": loyalty_program.id,
                    "active": loyalty_program.active,
                    "visits_for_reward": loyalty_program.visits_for_reward,
                    "reward_type": loyalty_program.reward_type,
                    "reward_value": (
                        str(loyalty_program.reward_value)
                        if loyalty_program.reward_value
                        else None
                    ),
                    "reward_description": loyalty_program.reward_description,
                    "created_at": (
                        loyalty_program.created_at.isoformat()
                        if loyalty_program.created_at
                        else None
                    ),
                    "updated_at": (
                        loyalty_program.updated_at.isoformat()
                        if loyalty_program.updated_at
                        else None
                    ),
                }
            ),
            200,
        )

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": "Database error", "details": str(e)}), 500
