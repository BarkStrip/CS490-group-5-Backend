from flask import Blueprint, request, jsonify, current_app
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from ..extensions import db
from ..models import AuthUser, Customers, Admins, SalonOwners, Employees, Cart
import bcrypt
import jwt
import datetime

auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth")


@auth_bp.route("/signup", methods=["POST"])
def signup_user():
    try:
        data = request.get_json(force=True)
        first_name = data.get("first_name")
        last_name = data.get("last_name")
        email = data.get("email")
        password = data.get("password")
        phone_number = data.get("phone_number")
        address = data.get("address") 
        role = data.get("role", "CUSTOMER").upper()
        salon_id = data.get("salon_id")

        # Validate required fields
        if not email or not password or not first_name or not phone_number:
            return jsonify({
                "status": "error",
                "message": "Missing required fields (email, password, first_name, phone_number)"
            }), 400
        
        # Validate role
        if role not in ["CUSTOMER", "ADMIN", "OWNER", "EMPLOYEE"]:
            return jsonify({
                "status": "error",
                "message": f"Role '{role}' is not a valid or supported role for this signup."
            }), 400
        
        # EMPLOYEE-specific validation
        if role == "EMPLOYEE":
            if not salon_id:
                return jsonify({
                    "status": "error",
                    "message": "Salon ID is required for employee registration"
                }), 400
            
            if not address:
                return jsonify({
                    "status": "error",
                    "message": "Address is required for employee registration"
                }), 400

        # Check if email already exists
        existing = db.session.scalar(select(AuthUser).where(AuthUser.email == email))
        if existing:
            return jsonify({
                "status": "error",
                "message": "Email already exists"
            }), 400

        # Hash password
        hashed_pw = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt())

        # Create AuthUser
        auth_user = AuthUser(
            email=email,
            password_hash=hashed_pw,
            role=role
        )
        db.session.add(auth_user)
        db.session.flush()

        # Create profile based on role
        if role == "CUSTOMER":
            profile = Customers(
                user_id=auth_user.id,
                first_name=first_name,
                last_name=last_name,
                phone_number=phone_number,
                address=address 
            )
            db.session.add(profile)
            new_cart = Cart(user_id=auth_user.id) 
            db.session.add(new_cart)

        elif role == "ADMIN":
            profile = Admins(
                user_id=auth_user.id,
                first_name=first_name,
                last_name=last_name,
                phone_number=phone_number,
                address=address 
            )
        elif role == "OWNER":
            profile = SalonOwners(
                user_id=auth_user.id,
                first_name=first_name,
                last_name=last_name,
                phone_number=phone_number,
                address=address 
            )
        elif role == "EMPLOYEE":
            profile = Employees(
                user_id=auth_user.id,
                salon_id=salon_id,
                first_name=first_name,
                last_name=last_name,
                phone_number=phone_number,
                address=address,
                employment_status="inactive"  # Pending salon owner approval
            )
        
        db.session.add(profile)
        db.session.commit()

        # Build response
        response_user = {
            "id": auth_user.id, 
            "first_name": first_name,
            "last_name": last_name,
            "email": email,
            "phone_number": phone_number,
            "address": address, 
            "role": role
        }
        
        # Add salon_id to response for employees
        if role == "EMPLOYEE":
            response_user["salon_id"] = salon_id
            response_user["employment_status"] = "inactive"

        return jsonify({
            "status": "success",
            "message": "User registered successfully",
            "user": response_user
        }), 201

    except IntegrityError as e:
        db.session.rollback()
        return jsonify({
            "status": "error",
            "message": "Database integrity error",
            "details": str(e.orig)
        }), 400

    except Exception as e:
        db.session.rollback()
        return jsonify({
            "status": "error",
            "message": "Internal server error",
            "details": str(e)
        }), 500


@auth_bp.route("/login", methods=["POST"])
def login_user():
    try:
        data = request.get_json(force=True)
        email = data.get("email")
        password = data.get("password")

        if not email or not password:
            return jsonify({
                "status": "error",
                "message": "Email and password required"
            }), 400

        user = db.session.scalar(select(AuthUser).where(AuthUser.email == email))
        if not user or not user.password_hash:
            return jsonify({
                "status": "error",
                "message": "Invalid credentials"
            }), 401

        stored_hash = user.password_hash
        if isinstance(stored_hash, str):
            stored_hash = stored_hash.encode("utf-8")

        if not bcrypt.checkpw(password.encode("utf-8"), stored_hash):
            return jsonify({
                "status": "error",
                "message": "Invalid credentials"
            }), 401

        payload = {
            "user_id": user.id,
            "email": user.email,
            "role": user.role,
            "exp": datetime.datetime.utcnow() + datetime.timedelta(hours=1)
        }
        token = jwt.encode(payload, current_app.config["SECRET_KEY"], algorithm="HS256")

        return jsonify({
            "status": "success",
            "message": "Login successful",
            "token": token
        }), 200

    except Exception as e:
        return jsonify({
            "status": "error",
            "message": "Internal server error",
            "details": str(e)
        }), 500


@auth_bp.route("/user-type/<int:user_id>", methods=["GET"])
def get_user_type(user_id):
    """
    GET /api/auth/user-type/<user_id>
    Purpose: Retrieve detailed user information including role, email, names, phone, address, etc.
    Input: user_id (integer) from the URL path.

    Behavior:
    - Returns comprehensive user data based on their role
    - Includes role-specific profile information
    - For CUSTOMER role: customer profile data
    - For EMPLOYEE role: employee profile + salon info
    - For ADMIN role: admin profile data
    - For OWNER role: owner profile data
    """
    try:
        # Get the auth user
        user = db.session.scalar(select(AuthUser).where(AuthUser.id == user_id))
        if not user:
            return jsonify({
                "status": "error",
                "message": f"No user found with ID {user_id}"
            }), 404

        # Base response structure
        response = {
            "status": "success",
            "user_id": user.id,
            "email": user.email,
            "role": user.role,
            "created_at": user.created_at.isoformat() if user.created_at else None,
            "updated_at": user.updated_at.isoformat() if user.updated_at else None,
            "first_name": None,
            "last_name": None,
            "phone_number": None,
            "address": None
        }

        # Get role-specific profile information and add to response
        if user.role == "CUSTOMER":
            customer = db.session.scalar(select(Customers).where(Customers.user_id == user_id))
            if customer:
                response["profile_id"] = customer.id
                response["first_name"] = customer.first_name
                response["last_name"] = customer.last_name
                response["phone_number"] = customer.phone_number
                response["address"] = customer.address

        elif user.role == "EMPLOYEE":
            employee = db.session.scalar(select(Employees).where(Employees.user_id == user_id))
            if employee:
                response["profile_id"] = employee.id
                response["first_name"] = employee.first_name
                response["last_name"] = employee.last_name
                response["phone_number"] = employee.phone_number
                response["address"] = employee.address
                response["employment_status"] = employee.employment_status
                response["salon_id"] = employee.salon_id

        elif user.role == "ADMIN":
            admin = db.session.scalar(select(Admins).where(Admins.user_id == user_id))
            if admin:
                response["profile_id"] = admin.id
                response["first_name"] = admin.first_name
                response["last_name"] = admin.last_name
                response["phone_number"] = admin.phone_number
                response["address"] = admin.address
                response["status"] = admin.status

        elif user.role == "OWNER":
            owner = db.session.scalar(select(SalonOwners).where(SalonOwners.user_id == user_id))
            if owner:
                response["profile_id"] = owner.id
                response["first_name"] = owner.first_name
                response["last_name"] = owner.last_name
                response["phone_number"] = owner.phone_number
                response["address"] = owner.address

        return jsonify(response), 200

    except Exception as e:
        return jsonify({
            "status": "error",
            "message": "Internal server error",
            "details": str(e)
        }), 500


@auth_bp.route("/check-email", methods=["POST"])
def check_email_exists():
    """
    Checks if an email already exists in the AuthUser table.
    """
    try:
        data = request.get_json(force=True)
        email = data.get("email")

        if not email:
            return jsonify({
                "status": "error",
                "message": "Email is required"
            }), 400

        existing = db.session.scalar(select(AuthUser).where(AuthUser.email == email))
        
        return jsonify({"exists": bool(existing)}), 200

    except Exception as e:
        return jsonify({
            "status": "error",
            "message": "Internal server error",
            "details": str(e)
        }), 500
