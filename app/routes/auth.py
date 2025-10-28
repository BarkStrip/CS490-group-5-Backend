from flask import Blueprint, request, jsonify, current_app
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from ..extensions import db
from ..models import Users, Customers, AuthUser
import bcrypt
import jwt
import datetime

auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth")

# -------------------------------------------------------------------------
# SIGNUP (Hash + Save)
# -------------------------------------------------------------------------
@auth_bp.route("/signup", methods=["POST"])
def signup_user():
    try:
        data = request.get_json(force=True)
        email = data.get("email")
        password = data.get("password")
        name = data.get("name")
        phone = data.get("phone")
        gender = data.get("gender")
        role = data.get("role", "CUSTOMER").upper()

        # --- Validate ---
        if not email or not password or not name:
            return jsonify({
                "status": "error",
                "message": "Missing required fields (email, password, name)"
            }), 400

        # --- Check duplicate ---
        existing = db.session.scalar(select(AuthUser).where(AuthUser.email == email))
        if existing:
            return jsonify({
                "status": "error",
                "message": "Email already exists"
            }), 400

        # --- Hash password securely ---
        hashed_pw = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt())

        # --- Insert into users ---
        user = Users()
        db.session.add(user)
        db.session.flush()  # to get user.id

        # --- Insert into customers ---
        customer = Customers(
            name=name,
            email=email,
            phone=phone,
            role=role
        )
        db.session.add(customer)
        db.session.flush()

        # --- Insert into auth_user ---
        auth_user = AuthUser(
            id=user.id,
            email=email,
            password_hash=hashed_pw,
            role=role
        )
        db.session.add(auth_user)
        db.session.commit()

        return jsonify({
            "status": "success",
            "message": "User registered successfully",
            "user": {
                "id": user.id,
                "name": name,
                "email": email,
                "phone": phone,
                "gender": gender,
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


# -------------------------------------------------------------------------
# LOGIN (Validate + Return JWT)
# -------------------------------------------------------------------------
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

        # --- Lookup user ---
        user = db.session.scalar(select(AuthUser).where(AuthUser.email == email))
        if not user or not user.password_hash:
            return jsonify({
                "status": "error",
                "message": "Invalid credentials"
            }), 401

        # --- Verify password ---
        if not bcrypt.checkpw(password.encode("utf-8"), user.password_hash):
            return jsonify({
                "status": "error",
                "message": "Invalid credentials"
            }), 401

        # --- Generate JWT ---
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

#-------------------------------------------------------------------------
#GET /api/auth/user-type/<user_id>
#Purpose:
#Given a user ID, return what type of user they are.
#This helps frontend features verify roles quickly.
#-------------------------------------------------------------------------

@auth_bp.route("/user-type/<int:user_id>", methods=["GET"])
def get_user_type(user_id):
    try:
        # Step 1: Look up in AuthUser table
        user = db.session.scalar(select(AuthUser).where(AuthUser.id == user_id))
        if not user:
            return jsonify({
                "status": "error",
                "message": f"No user found with ID {user_id}"
            }), 404

        # Step 2: Return the user's role
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