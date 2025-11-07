from flask import Blueprint, jsonify, request, current_app
from sqlalchemy import select, func
from app.extensions import db
from ...models import (
    Customers, Salon, LoyaltyAccount, LoyaltyProgram, Appointment,
     LoyaltyTransaction, Promos
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



@loyalty_bp.route("/customers/<int:customer_id>/dashboard", methods=['GET'])
def get_loyalty_dashboard(customer_id):
    """
    --- Endpoint 1: Customer Loyalty Dashboard (Aggregate) ---
    
    Powers the top-level summary cards in your UI (e.g., "Lifetime Points", 
    "Active Programs", "Total Visits").
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
            .where(Appointment.status == 'COMPLETED') 
        )
        
     
        
        response = {
            "current_total_points": current_total_points, 
            "active_programs_count": active_programs_count,
            "total_visits_all_time": total_visits or 0
        }
        return jsonify(response)
        
    except Exception as e:
        current_app.logger.error(f"Failed to get loyalty dashboard for customer {customer_id}: {e}")
        return jsonify({"status": "error", "message": "Failed to get dashboard", "details": str(e)}), 500


@loyalty_bp.route("/customers/<int:customer_id>/programs", methods=['GET'])
def get_customer_loyalty_programs(customer_id):
    """
    --- Endpoint 2: Customer's Loyalty Programs List ---
    
    Powers the main list in your UI (e.g., the "Jade Boutique" card).
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
            .where(LoyaltyProgram.active == True) 
        )
        
        results = db.session.execute(stmt).all()
        
        response_list = []
        for acc, salon, program in results:
            
            visits_at_salon = db.session.scalar(
                select(func.count(Appointment.id))
                .where(Appointment.customer_id == customer_id)
                .where(Appointment.salon_id == salon.id)
                .where(Appointment.status == 'COMPLETED') 
            )

            points_for_reward = getattr(program, 'points_for_reward', 1000) 
            points_away = max(0, points_for_reward - acc.points)
            
            response_list.append({
                "salon_id": salon.id,
                "salon_name": salon.name,
                "current_points": acc.points,
                "total_visits_at_salon": visits_at_salon or 0,
                "program_details": {
                    "description": getattr(program, 'reward_description', f"{points_for_reward} points for reward"),
                    "points_per_dollar": float(getattr(program, 'points_per_dollar', 1)), 
                },
                "next_reward_progress": {
                    "points_to_next_reward": points_for_reward,
                    "points_away": points_away
                }
            })
            
        return jsonify(response_list)

    except Exception as e:
        current_app.logger.error(f"Failed to get loyalty programs for customer {customer_id}: {e}")
        return jsonify({"status": "error", "message": "Failed to get programs", "details": str(e)}), 500


@loyalty_bp.route("/customers/<int:customer_id>/programs/<int:salon_id>/activity", methods=['GET'])
def get_loyalty_activity(customer_id, salon_id):
    """
    --- Endpoint 3: Salon-Specific Recent Activity ---
    
    This queries the LoyaltyTransaction table 

    """
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
           
            activity_list.append({
                "activity_id": f"txn_{txn.id}",
                "date": txn.created_at.isoformat(),
                "description": txn.reason, 
                "points_change": txn.points_change 
            })

        return jsonify(activity_list)

    except Exception as e:
        current_app.logger.error(f"Failed to get loyalty activity for cust {customer_id}, salon {salon_id}: {e}")
        return jsonify({"status": "error", "message": "Failed to get activity", "details": str(e)}), 500


@loyalty_bp.route("/customers/<int:customer_id>/programs/<int:salon_id>/rewards", methods=['GET'])
def get_available_rewards(customer_id, salon_id):
    """
    --- Endpoint 4: Get Available Rewards ---
    
    Fetches loyalty rewards a customer can redeem with their points
    for the "Reward" tab.
    """
    try:
        account = get_loyalty_account(customer_id, salon_id)
        if not account:
            return jsonify({"status": "error", "message": "Loyalty account not found"}), 404
        
        program = db.session.scalar(
            select(LoyaltyProgram).where(LoyaltyProgram.salon_id == salon_id)
        )
        if not program or not program.active:
            return jsonify({"status": "error", "message": "No active loyalty program for this salon"}), 404

    
        
        points_for_reward = getattr(program, 'points_for_reward', 1000)
        can_redeem = account.points >= points_for_reward

        reward_list = [
            {
                "reward_id": f"prog_{program.id}_main_reward", 
                "description": getattr(program, 'reward_description', f"{program.reward_value}% off"),
                "points_cost": points_for_reward,
                "is_redeemable": can_redeem,
                "reward_type": str(program.reward_type), 
                "reward_value": float(program.reward_value) 
            }
           
        ]
        
        return jsonify(reward_list)

    except Exception as e:
        current_app.logger.error(f"Failed to get available rewards for cust {customer_id}, salon {salon_id}: {e}")
        return jsonify({"status": "error", "message": "Failed to get rewards", "details": str(e)}), 500


@loyalty_bp.route("/customers/<int:customer_id>/programs/<int:salon_id>/redeem", methods=['POST'])
def redeem_loyalty_reward(customer_id, salon_id):
    """
    --- Endpoint 5: Redeem Loyalty Reward ---
    
    The action of spending points to get a reward.
    This deducts points, logs the transaction, and creates a
    one-time promo code.
    """
    try:
        data = request.json
        reward_id = data.get('reward_id')
        if not reward_id:
            return jsonify({"status": "error", "message": "reward_id is required"}), 400

        account = get_loyalty_account(customer_id, salon_id)
        if not account:
            return jsonify({"status": "error", "message": "Loyalty account not found"}), 404
            
        
        program = db.session.scalar(select(LoyaltyProgram).where(LoyaltyProgram.salon_id == salon_id))
        if not program:
             return jsonify({"status": "error", "message": "Loyalty program not found"}), 404
       
        points_cost = getattr(program, 'points_for_reward', 1000)
        
        
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
            description=f"Loyalty Reward for Customer {customer_id} from Salon {salon_id}"
        )
        db.session.add(new_promo)
        
        db.session.commit()
        
        return jsonify({
            "status": "success",
            "message": "Reward redeemed successfully!",
            "data": {
                "new_points_balance": account.points,
                "promo_code_generated": new_promo.code,
                "expires_at": new_promo.expires_at.isoformat()
            }
        }), 201

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Failed to redeem reward for cust {customer_id}, salon {salon_id}: {e}")
        return jsonify({"status": "error", "message": "Failed to redeem reward", "details": str(e)}), 500