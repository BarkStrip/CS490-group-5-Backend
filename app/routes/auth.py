from flask import Blueprint, request, jsonify, current_app
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from ..extensions import db
from ..models import AuthUser, Customers, Admins, SalonOwners
import bcrypt
import jwt
import datetime

auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth")


@auth_bp.route("/signup", methods=["POST"])
def signup_user():
    try:
        data = request.get_json(force=True)
        name = data.get("first_name")
        last_name = data.get("last_name")
        email = data.get("email")
        password = data.get("password")
        phone = data.get("phone_number")
        address = data.get("address") 
        role = data.get("role", "CUSTOMER").upper()

        salon_id = data.get("salon_id")

        if not email or not password or not name or not phone:
            return jsonify({
                "status": "error",
                "message": "Missing required fields (email, password, name)"
            }), 400
        
        if role not in ["CUSTOMER", "ADMIN", "OWNER", "EMPLOYEE"]:
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
        
        if role == "EMPLOYEE" and not salon_id:
            return jsonify({
                "status": "error",
                "message": "Salon ID is required for employee registration"
            }), 400
        
        if role == "EMPLOYEE" and not address:
            return jsonify({
                "status": "error",
                "message": "Address is required for employee registration"
            }), 400



        auth_user = AuthUser(
            email=email,
            password_hash=hashed_pw,
            role=role
        )
        db.session.add(auth_user)
        db.session.flush()

 
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

        elif role == "EMPLOYEE":
            profile = Employees(
                user_id=auth_user.id,
                salon_id=salon_id,
                first_name=first_name,
                last_name=last_name,
                phone_number=phone,
                address=address,
                employment_status="deactive"
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
    try:
        user = db.session.scalar(select(AuthUser).where(AuthUser.id == user_id))
        if not user:
            return jsonify({
                "status": "error",
                "message": f"No user found with ID {user_id}"
            }), 404

        return jsonify({
            "status": "success",
            "user_id": user_id,
            "email": user.email,
            "role": user.role
        }), 200

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