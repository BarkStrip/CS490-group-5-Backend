from flask import Blueprint, request, jsonify
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from ..extensions import db
from ..models import Users, Customers, AuthUser

auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth")

# -------------------------------------------------------------------------
# SIGNUP ENDPOINT
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

        # --- Validate input ---
        if not email or not password or not name:
            return jsonify({
                "status": "error",
                "message": "Missing required fields (email, password, name)"
            }), 400

        # --- Check duplicate in auth_user ---
        existing = db.session.scalar(select(AuthUser).where(AuthUser.email == email))
        if existing:
            return jsonify({
                "status": "error",
                "message": "Email already exists"
            }), 400

        # --- Step 1: Insert into users ---
        user = Users()
        db.session.add(user)
        db.session.flush()  # generates user.id

        # --- Step 2: Insert into customers ---
        customer = Customers(
            name=name,
            email=email,
            phone=phone,
            role=role
        )
        db.session.add(customer)
        db.session.flush()

        # --- Step 3: Insert into auth_user ---
        auth_user = AuthUser(
            id=user.id,
            email=email,
            password_hash=None,
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
