# app/utils/salon_cleanup.py
from app.extensions import db
from sqlalchemy import delete, select
from app.models import (
    Salon, Service, Product, Employees, Appointment, AppointmentImage,
    Order, OrderItem, CartItem, Payment, Review, ReviewReply, ReviewToken,
    LoyaltyAccount, LoyaltyProgram, LoyaltyTransaction, SalonHours,
    SalonImage, SalonVerify, CancelPolicy, NoshowPolicy, TimeBlock,
    EmpAvail, Message, UserImage, SalonOwners, AuthUser
)

def hard_delete_salon(salon_id: int):
    """
    Completely eliminates a salon and ALL its associated data.
    
    Logic:
    1. Deletes all child data (Appointments, Orders, Staff, etc.)
    2. Deletes the Salon itself.
    3. Checks if the Salon Owner has any other salons.
    4. If no other salons exist, deletes the SalonOwner profile AND AuthUser account.
    """
    try:
        print(f"⚠ STARTING HARD DELETE FOR SALON ID: {salon_id}")

        # --------------------------------------------------
        # 1. CLEANUP COMMERCE (Orders, Cart Items, Payments)
        # --------------------------------------------------
        # Delete Cart Items linked to this salon's products/services
        db.session.execute(
            delete(CartItem).where(
                CartItem.product_id.in_(
                    select(Product.id).where(Product.salon_id == salon_id)
                )
            )
        )
        db.session.execute(
            delete(CartItem).where(
                CartItem.service_id.in_(
                    select(Service.id).where(Service.salon_id == salon_id)
                )
            )
        )

        # Delete Order Items and Payments linked to Salon's orders
        orders_subquery = select(Order.id).where(Order.salon_id == salon_id)
        
        db.session.execute(
            delete(OrderItem).where(OrderItem.order_id.in_(orders_subquery))
        )
        db.session.execute(
            delete(Payment).where(Payment.order_id.in_(orders_subquery))
        )
        # Finally delete the Orders
        db.session.execute(delete(Order).where(Order.salon_id == salon_id))


        # --------------------------------------------------
        # 2. CLEANUP APPOINTMENTS
        # --------------------------------------------------
        appt_subquery = select(Appointment.id).where(Appointment.salon_id == salon_id)
        
        # Delete images linked to appointments
        db.session.execute(
            delete(AppointmentImage).where(AppointmentImage.appointment_id.in_(appt_subquery))
        )
        # Delete the appointments
        db.session.execute(delete(Appointment).where(Appointment.salon_id == salon_id))


        # --------------------------------------------------
        # 3. CLEANUP STAFF (Employees and their data)
        # --------------------------------------------------
        emp_subquery = select(Employees.id).where(Employees.salon_id == salon_id)
        
        db.session.execute(delete(EmpAvail).where(EmpAvail.employee_id.in_(emp_subquery)))
        db.session.execute(delete(TimeBlock).where(TimeBlock.employee_id.in_(emp_subquery)))
        db.session.execute(delete(Message).where(Message.employee_id.in_(emp_subquery)))
        
        # Delete the Employees themselves
        db.session.execute(delete(Employees).where(Employees.salon_id == salon_id))


        # --------------------------------------------------
        # 4. CLEANUP LOYALTY & REVIEWS
        # --------------------------------------------------
        # Loyalty
        loyalty_acc_subquery = select(LoyaltyAccount.id).where(LoyaltyAccount.salon_id == salon_id)
        db.session.execute(
            delete(LoyaltyTransaction).where(LoyaltyTransaction.loyalty_account_id.in_(loyalty_acc_subquery))
        )
        db.session.execute(delete(LoyaltyAccount).where(LoyaltyAccount.salon_id == salon_id))
        db.session.execute(delete(LoyaltyProgram).where(LoyaltyProgram.salon_id == salon_id))

        # Reviews
        review_subquery = select(Review.id).where(Review.salon_id == salon_id)
        db.session.execute(
            delete(ReviewReply).where(ReviewReply.review_id.in_(review_subquery))
        )
        db.session.execute(delete(Review).where(Review.salon_id == salon_id))
        db.session.execute(delete(ReviewToken).where(ReviewToken.salon_id == salon_id))


        # --------------------------------------------------
        # 5. CLEANUP INVENTORY (Services & Products)
        # --------------------------------------------------
        db.session.execute(delete(Service).where(Service.salon_id == salon_id))
        db.session.execute(delete(Product).where(Product.salon_id == salon_id))


        # --------------------------------------------------
        # 6. CLEANUP SALON METADATA
        # --------------------------------------------------
        db.session.execute(delete(SalonHours).where(SalonHours.salon_id == salon_id))
        db.session.execute(delete(SalonImage).where(SalonImage.salon_id == salon_id))
        db.session.execute(delete(SalonVerify).where(SalonVerify.salon_id == salon_id))
        db.session.execute(delete(CancelPolicy).where(CancelPolicy.salon_id == salon_id))
        db.session.execute(delete(NoshowPolicy).where(NoshowPolicy.salon_id == salon_id))
        # Salon-level time blocks (if any exist not linked to employees)
        db.session.execute(delete(TimeBlock).where(TimeBlock.salon_id == salon_id))


        # --------------------------------------------------
        # 7. DELETE THE SALON
        # --------------------------------------------------
        salon = db.session.get(Salon, salon_id)
        if not salon:
            print(f"❌ Salon {salon_id} not found.")
            return False
            
        owner_id = salon.salon_owner_id  # Save Owner ID for Step 8
        
        # Clear relationships (Many-to-Many types)
        salon.type = [] 
        
        db.session.delete(salon)
        db.session.flush() # Ensure salon is strictly gone before checking owner's other salons
        print(f"✅ Deleted Salon {salon_id}")


        # --------------------------------------------------
        # 8. SCENARIO B: CLEANUP OWNER (If no salons left)
        # --------------------------------------------------
        # Check if this owner has any other salons left
        remaining_salons = db.session.scalars(
            select(Salon.id).where(Salon.salon_owner_id == owner_id)
        ).all()

        if not remaining_salons:
            print(f"ℹ Owner {owner_id} has no other salons. Deleting Owner Account...")
            
            # Get the owner profile
            owner = db.session.get(SalonOwners, owner_id)
            if owner:
                user_id = owner.user_id
                
                # Delete Owner Profile
                db.session.delete(owner)
                db.session.flush()

                # Delete Login Account (AuthUser)
                # Note: This cascades to Admins table if configured, ensuring full cleanup
                auth_user = db.session.get(AuthUser, user_id)
                if auth_user:
                    db.session.delete(auth_user)
                    
                print(f"✅ Deleted Owner Profile {owner_id} and AuthUser {user_id}")
        else:
            print(f"ℹ Owner {owner_id} has {len(remaining_salons)} other salon(s). Account preserved.")

        db.session.commit()
        print("✅ HARD DELETE COMPLETED SUCCESSFULLY")
        return True

    except Exception as e:
        db.session.rollback()
        print(f"❌ FAILED TO DELETE SALON ID {salon_id}: {str(e)}")
        # Raise error so the calling API knows it failed
        raise e