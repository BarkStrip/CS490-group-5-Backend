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
    """
    Get customer loyalty dashboard summary
    ---
    summary: Returns aggregated loyalty stats for the customer
    description: Powers the top-level summary cards in your UI (e.g., "Lifetime Points", "Active Programs", "Total Visits").
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
            .where(LoyaltyProgram.active == 1)  # only active programs
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
            points_away = max(0, points_for_reward - acc.points)

            # safe handling for points_per_dollar (can be NULL)
            raw_ppd = getattr(program, "points_per_dollar", None)
            if raw_ppd is None:
                ppd_value = 1.0  # default display if not configured
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
                            program,
                            "reward_description",
                            f"{points_for_reward} points for reward",
                        ),
                        "points_per_dollar": ppd_value,
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


@loyalty_bp.route("/customers/<int:customer_id>/programs/<int:salon_id>/activity", methods=["GET"])
def get_loyalty_activity(customer_id, salon_id):
    """
    Get recent loyalty activity for a customer at a specific salon
    ---
    summary: Returns loyalty transaction history
    description: Retrieves the most recent 20 loyalty transactions for a customer and salon.
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


@loyalty_bp.route("/customers/<int:customer_id>/programs/<int:salon_id>/rewards", methods=["GET"])
def get_available_rewards(customer_id, salon_id):
    """
    Get available loyalty rewards
    ---
    summary: Returns rewards a customer can redeem using points
    description: Fetches loyalty rewards available for the customer's active salon program.
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

        points_for_reward = getattr(program, "points_for_reward", None)
        if points_for_reward is None:
            points_for_reward = 1000

        can_redeem = account.points >= points_for_reward

        rv = program.reward_value
        reward_value = float(rv) if rv is not None else 0.0

        reward_list = [
            {
                "reward_id": f"prog_{program.id}_main_reward",
                "description": getattr(
                    program, "reward_description", f"{reward_value}% off"
                ),
                "points_cost": points_for_reward,
                "is_redeemable": can_redeem,
                "reward_type": str(program.reward_type),
                "reward_value": reward_value,
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


@loyalty_bp.route("/customers/<int:customer_id>/programs/<int:salon_id>/redeem", methods=["POST"])
def redeem_loyalty_reward(customer_id, salon_id):
    """
    Redeem a loyalty reward
    ---
    summary: Spend points to redeem a reward
    description: Deducts points, logs the transaction, and generates a one-time promo code for the customer.
    """
    try:
        data = request.json or {}
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
            # Return "empty" program structure when none exists yet
            return (
                jsonify(
                    {
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
                    "points_per_dollar": (
                        float(loyalty_program.points_per_dollar)
                        if loyalty_program.points_per_dollar is not None
                        else None
                    ),
                    "points_for_reward": loyalty_program.points_for_reward,
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
    Input JSON can include:
      * active (0 or 1)
      * points_per_dollar (decimal)
      * points_for_reward (int)
      * visits_for_reward (int)
      * reward_type ('PERCENT', 'FIXED_AMOUNT', or 'FREE_ITEM')
      * reward_value (decimal)
      * reward_description (string)
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
            # Create new loyalty program (initially "blank"/inactive)
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

        if "points_per_dollar" in data:
            ppd = data.get("points_per_dollar")
            try:
                if ppd is None or ppd == "":
                    loyalty_program.points_per_dollar = None
                else:
                    loyalty_program.points_per_dollar = Decimal(str(ppd))
            except Exception:
                return (
                    jsonify(
                        {
                            "error": "Invalid value",
                            "message": "points_per_dollar must be a valid decimal number",
                        }
                    ),
                    400,
                )

        if "points_for_reward" in data:
            pfr = data.get("points_for_reward")
            if pfr is not None:
                try:
                    pfr_int = int(pfr)
                except (TypeError, ValueError):
                    return (
                        jsonify(
                            {
                                "error": "Invalid value",
                                "message": "points_for_reward must be an integer",
                            }
                        ),
                        400,
                    )
                if pfr_int < 0:
                    return (
                        jsonify(
                            {
                                "error": "Invalid value",
                                "message": "points_for_reward must be non-negative",
                            }
                        ),
                        400,
                    )
                loyalty_program.points_for_reward = pfr_int

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
                loyalty_program.reward_value = (
                    None
                    if reward_value is None or reward_value == ""
                    else Decimal(str(reward_value))
                )
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
                    "points_per_dollar": (
                        float(loyalty_program.points_per_dollar)
                        if loyalty_program.points_per_dollar is not None
                        else None
                    ),
                    "points_for_reward": loyalty_program.points_for_reward,
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


@loyalty_bp.route("/cart/check-rewards", methods=["POST"])
def check_cart_rewards():
    """
    Batch checks rewards for multiple salons in the cart.
    Input: { "customer_id": 123, "salon_ids": [1, 2, 5] }
    """
    try:
        data = request.json or {}
        customer_id = data.get("customer_id")
        salon_ids = data.get("salon_ids", [])
        
        # Remove duplicates from salon_ids
        salon_ids = list(set(salon_ids))

        results = {}

        for salon_id in salon_ids:
            # 1. Reuse your existing helper
            account = get_loyalty_account(customer_id, salon_id)
            
            # 2. Get Program Rules
            program = db.session.scalar(
                select(LoyaltyProgram)
                .where(LoyaltyProgram.salon_id == salon_id)
                .where(LoyaltyProgram.active == 1)
                .where(LoyaltyProgram.program_type == 'POINTS')
            )

            # Default Response (No points)
            results[salon_id] = {
                "available": False,
                "info_text": "No points available",
                "max_discount": 0.00,
                "points_balance": 0
            }

            if account and program:
                points = account.points
                # Handle potential None values in DB
                points_req = program.points_for_reward or 1000
                reward_val = float(program.reward_value or 0)

                # 3. Calculate Stacking Logic (e.g., 1000 pts = $10. User has 2000 pts = $20)
                if points_req > 0 and points >= points_req:
                    # Integer division to see how many "rewards" they can afford
                    chunks = points // points_req
                    max_discount = chunks * reward_val
                    
                    results[salon_id] = {
                        "available": True,
                        "info_text": f"{points} points available. Eligible for ${max_discount:.2f} off.",
                        "max_discount": max_discount,
                        "points_balance": points
                    }
                elif points > 0:
                    needed = points_req - points
                    results[salon_id] = {
                        "available": False,
                        "info_text": f"{points} points. {needed} more needed for reward.",
                        "max_discount": 0.00,
                        "points_balance": points
                    }

        return jsonify(results), 200

    except Exception as e:
        current_app.logger.error(f"Error checking cart rewards: {e}")
        return jsonify({"status": "error", "details": str(e)}), 500
    

def process_loyalty_for_order(customer_id, cart_items, applied_rewards):
    """
    1. Deducts points for rewards used.
    2. Accrues new points based on money spent.
    Call this inside your create_order route after payment success.
    """
    try:
        # --- A. DEDUCT POINTS (If user selected a discount) ---
        for reward in applied_rewards:
            salon_id = reward.get('salon_id')
            discount_amount = float(reward.get('discount_amount', 0))
            
            program = db.session.scalar(
                select(LoyaltyProgram).where(LoyaltyProgram.salon_id == salon_id)
            )
            
            if program and discount_amount > 0:
                # Reverse math: How many points was that discount worth?
                # If $5 discount = 50 points, then Points = (Discount / RewardVal) * PointsReq
                rv = float(program.reward_value or 1)
                req = program.points_for_reward or 1000
                
                points_to_deduct = int((discount_amount / rv) * req)
                
                account = get_loyalty_account(customer_id, salon_id)
                if account and account.points >= points_to_deduct:
                    account.points -= points_to_deduct
                    
                    # Log Transaction
                    deduct_txn = LoyaltyTransaction(
                        loyalty_account_id=account.id,
                        points_change=-points_to_deduct,
                        reason=f"Redeemed ${discount_amount} off at checkout"
                    )
                    db.session.add(deduct_txn)

        # --- B. ACCRUE POINTS (Earn points on spend) ---
        # Group spend by salon
        salon_spend = {}
        for item in cart_items:
            # Check variable names based on your cart structure
            s_id = item.get('salon_id') or item.get('service_salon_id')
            # Only accrue on the actual price paid (ignoring the discount for now, or based on business logic)
            price = float(item.get('unit_price', 0)) * int(item.get('qty', 1))
            
            if s_id:
                salon_spend[s_id] = salon_spend.get(s_id, 0) + price

        for salon_id, amount_spent in salon_spend.items():
            program = db.session.scalar(
                 select(LoyaltyProgram).where(LoyaltyProgram.salon_id == salon_id)
            )
            
            # Create account if it doesn't exist yet
            account = get_loyalty_account(customer_id, salon_id)
            if not account:
                account = LoyaltyAccount(user_id=customer_id, salon_id=salon_id, points=0)
                db.session.add(account)
                db.session.flush() # Get ID

            if program and program.active and program.points_per_dollar:
                points_to_add = int(amount_spent * float(program.points_per_dollar))
                
                if points_to_add > 0:
                    account.points += points_to_add
                    
                    add_txn = LoyaltyTransaction(
                        loyalty_account_id=account.id,
                        points_change=points_to_add,
                        reason=f"Earned from order (Spent ${amount_spent})"
                    )
                    db.session.add(add_txn)
        
        # Commit all changes (Deductions + Accruals)
        db.session.commit()
        return True

    except Exception as e:
        current_app.logger.error(f"Loyalty processing failed: {e}")
        db.session.rollback() # Don't break the order if loyalty fails, just log it
        return False