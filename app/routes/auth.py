from flask import Blueprint, request, jsonify, current_app
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from ..extensions import db
from ..models import AuthUser, Customers, Admins, SalonOwners, Employees
import bcrypt
import jwt
import datetime

auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth")


@auth_bp.route("/signup", methods=["POST"])
def signup_user():
    try:
        data = request.get_json(force=True)
        email = data.get("email")
        password = data.get("password")
        name = data.get("name")
        phone = data.get("phone")
        address = data.get("address") 
        role = data.get("role", "CUSTOMER").upper()

        if not email or not password or not name:
            return jsonify({
                "status": "error",
                "message": "Missing required fields (email, password, name)"
            }), 400
        
        if role not in ["CUSTOMER", "ADMIN", "OWNER"]:
            return jsonify({
                "status": "error",
                "message": f"Role '{role}' is not a valid or supported role for this signup."
            }), 400

        existing = db.session.scalar(select(AuthUser).where(AuthUser.email == email))
        if existing:
            return jsonify({
                "status": "error",
                "message": "Email already exists"
            }), 400

        hashed_pw = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt())


        auth_user = AuthUser(
            email=email,
            password_hash=hashed_pw,
            role=role
        )
        db.session.add(auth_user)
        db.session.flush()

        first_name = ""
        last_name = ""
        if name:
            parts = name.split(" ", 1)
            first_name = parts[0]
            if len(parts) > 1:
                last_name = parts[1]


        if role == "CUSTOMER":
            profile = Customers(
                user_id=auth_user.id,
                first_name=first_name,
                last_name=last_name,
                phone_number=phone,
                address=address 
            )
        elif role == "ADMIN":
            profile = Admins(
                user_id=auth_user.id,
                first_name=first_name,
                last_name=last_name,
                phone_number=phone,
                address=address 
            )
        elif role == "OWNER":
            profile = SalonOwners(
                user_id=auth_user.id,
                first_name=first_name,
                last_name=last_name,
                phone_number=phone,
                address=address 
            )
        db.session.add(profile)
        
        db.session.commit()

        return jsonify({
            "status": "success",
            "message": "User registered successfully",
            "user": {
                "id": auth_user.id, 
                "name": name,
                "email": email,
                "phone": phone,
                "address": address, 
                "role": role
            }
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