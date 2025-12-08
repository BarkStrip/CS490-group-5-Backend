from flask import Blueprint, request, jsonify, current_app
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from ..extensions import db
from ..models import AuthUser, Customers, Admins, SalonOwners, Employees, Cart
import bcrypt
import jwt
from datetime import datetime, timedelta, timezone
from app.services.email_service import email_service
auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth")
import random
import string

# For calculating the age
def calculate_age(date_of_birth):
    """Calculate age from date of birth"""
    if not date_of_birth:
        return None
    
    if isinstance(date_of_birth, str):
        date_of_birth = datetime.strptime(date_of_birth, '%Y-%m-%d').date()
    
    today = datetime.now().date()
    age = today.year - date_of_birth.year
    
    if (today.month, today.day) < (date_of_birth.month, date_of_birth.day):
        age -= 1
    
    return age

@auth_bp.route("/signup", methods=["POST"])
def signup_user():
    """
    Register a new user account
    ---
    tags:
      - Authentication
    parameters:
      - in: body
        name: body
        required: true
        schema:
          type: object
          required:
            - email
            - password
            - name
          properties:
            email:
              type: string
              format: email
              description: User email address
            password:
              type: string
              format: password
              description: User password (will be hashed)
            name:
              type: string
              description: User full name
            phone:
              type: string
              description: User phone number
            gender:
              type: string
              enum: [Male, Female, Other]
            role:
              type: string
              enum: [CUSTOMER, OWNER, EMPLOYEE, ADMIN]
              default: CUSTOMER
    responses:
      201:
        description: User registered successfully
        schema:
          type: object
          properties:
            status:
              type: string
              example: success
            message:
              type: string
            user:
              $ref: '#/definitions/User'
      400:
        description: Missing required fields or email already exists
        schema:
          $ref: '#/definitions/Error'
      500:
        description: Internal server error
        schema:
          $ref: '#/definitions/Error'
    """
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
        date_of_birth_str = data.get("date_of_birth")
        gender = data.get("gender") 

        # Validate required fields
        if not email or not password or not first_name or not phone_number:
            return (
                jsonify(
                    {
                        "status": "error",
                        "message": "Missing required fields (email, password, first_name, phone_number)",
                    }
                ),
                400,
            )
        if role == "CUSTOMER":
                    if not date_of_birth_str or not gender:
                        return (
                            jsonify(
                                {
                                    "status": "error",
                                    "message": "Date of birth and gender are required for customer registration",
                                }
                            ),
                            400,
                        )
                    
                    # Validate and process DOB
                    try:
                        date_of_birth = datetime.strptime(date_of_birth_str, '%Y-%m-%d').date()
                        age = calculate_age(date_of_birth)
                        
                        if age < 13:
                            return (
                                jsonify(
                                    {
                                        "status": "error",
                                        "message": "You must be at least 13 years old to create an account",
                                    }
                                ),
                                400,
                            )
                        
                        if age > 120:
                            return (
                                jsonify(
                                    {
                                        "status": "error",
                                        "message": "Please enter a valid date of birth",
                                    }
                                ),
                                400,
                            )
                    except ValueError:
                        return (
                            jsonify(
                                {
                                    "status": "error",
                                    "message": "Invalid date format. Please use YYYY-MM-DD",
                                }
                            ),
                            400,
                        )
                    
                    # Validate gender
                    if gender not in ['Male', 'Female', 'Other']:
                        return (
                            jsonify(
                                {
                                    "status": "error",
                                    "message": "Gender must be Male, Female, or Other",
                                }
                            ),
                            400,
                        )
        # Validate role
        if role not in ["CUSTOMER", "ADMIN", "OWNER", "EMPLOYEE"]:
            return (
                jsonify(
                    {
                        "status": "error",
                        "message": f"Role '{role}' is not a valid or supported role for this signup.",
                    }
                ),
                400,
            )

        # EMPLOYEE-specific validation
        if role == "EMPLOYEE":
            if not salon_id:
                return (
                    jsonify(
                        {
                            "status": "error",
                            "message": "Salon ID is required for employee registration",
                        }
                    ),
                    400,
                )

            if not address:
                return (
                    jsonify(
                        {
                            "status": "error",
                            "message": "Address is required for employee registration",
                        }
                    ),
                    400,
                )

        # Check if email already exists
        existing = db.session.scalar(select(AuthUser).where(AuthUser.email == email))
        if existing:
            return jsonify({"status": "error", "message": "Email already exists"}), 400

        # Hash password
        hashed_pw = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt())

        # Create AuthUser
        auth_user = AuthUser(email=email, password_hash=hashed_pw, role=role)
        db.session.add(auth_user)
        db.session.flush()  # Flush to get the auth_user.id needed for foreign key relationships

        # Create profile based on role
        if role == "CUSTOMER":
            profile = Customers(
                user_id=auth_user.id,
                first_name=first_name,
                last_name=last_name,
                phone_number=phone_number,
                address=address,
                date_of_birth=date_of_birth,  
                gender=gender,                
                age=age,
            )
            db.session.add(profile)
            db.session.flush()
            new_cart = Cart(user_id=profile.id)
            db.session.add(new_cart)

        elif role == "ADMIN":
            profile = Admins(
                user_id=auth_user.id,
                first_name=first_name,
                last_name=last_name,
                phone_number=phone_number,
                address=address,
            )
        elif role == "OWNER":
            profile = SalonOwners(
                user_id=auth_user.id,
                first_name=first_name,
                last_name=last_name,
                phone_number=phone_number,
                address=address,
            )
        elif role == "EMPLOYEE":
            profile = Employees(
                user_id=auth_user.id,
                salon_id=salon_id,
                first_name=first_name,
                last_name=last_name,
                phone_number=phone_number,
                address=address,
                employment_status="inactive",  # Pending salon owner approval
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
            "role": role,
        }
        if role == "CUSTOMER":
            response_user["date_of_birth"] = date_of_birth.isoformat()
            response_user["gender"] = gender
            response_user["age"] = age
        # Add salon_id to response for employees
        if role == "EMPLOYEE":
            response_user["salon_id"] = salon_id
            response_user["employment_status"] = "inactive"

        return (
            jsonify(
                {
                    "status": "success",
                    "message": "User registered successfully",
                    "user": response_user,
                }
            ),
            201,
        )

    except IntegrityError as e:
        print("IntegrityError ORIGINAL:", e.orig)
        db.session.rollback()
        return (
            jsonify(
                {
                    "status": "error",
                    "message": "Database integrity error",
                    "details": str(e.orig),
                }
            ),
            400,
        )

    except Exception as e:
        db.session.rollback()
        return (
            jsonify(
                {
                    "status": "error",
                    "message": "Internal server error",
                    "details": str(e),
                }
            ),
            500,
        )


@auth_bp.route("/login", methods=["POST"])
def login_user():
    """
    Login user and receive JWT token
    ---
    tags:
      - Authentication
    parameters:
      - in: body
        name: body
        required: true
        schema:
          type: object
          required:
            - email
            - password
          properties:
            email:
              type: string
              format: email
            password:
              type: string
              format: password
    responses:
      200:
        description: Login successful, JWT token returned
        schema:
          type: object
          properties:
            status:
              type: string
              example: success
            message:
              type: string
            token:
              type: string
              description: JWT token valid for 1 hour
      401:
        description: Invalid credentials
        schema:
          $ref: '#/definitions/Error'
      500:
        description: Internal server error
        schema:
          $ref: '#/definitions/Error'
    """
    try:
        data = request.get_json(force=True)
        email = data.get("email")
        password = data.get("password")
        if not email or not password:
            return (
                jsonify({"status": "error", "message": "Email and password required"}),
                400,
            )

        user = db.session.scalar(select(AuthUser).where(AuthUser.email == email))
        if not user or not user.password_hash:
            return jsonify({"status": "error", "message": "Invalid credentials"}), 401

        stored_hash = user.password_hash
        if isinstance(stored_hash, str):
            stored_hash = stored_hash.encode("utf-8")

        if not bcrypt.checkpw(password.encode("utf-8"), stored_hash):
            return jsonify({"status": "error", "message": "Invalid credentials"}), 401

        payload = {
            "user_id": user.id,
            "email": user.email,
            "role": user.role,
            "exp": datetime.now(timezone.utc) + timedelta(hours=1),    
                  }
        token = jwt.encode(payload, current_app.config["SECRET_KEY"], algorithm="HS256")

        return (
            jsonify(
                {"status": "success", "message": "Login successful", "token": token}
            ),
            200,
        )

    except Exception as e:
        print(f"Login Error: {str(e)}") 
        return (
            jsonify(
                {
                    "status": "error",
                    "message": "Internal server error",
                    "details": str(e),
                }
            ),
            500,
        )


@auth_bp.route("/user-type/<int:user_id>", methods=["GET"])
def get_user_type(user_id):
    """
    Get user type/role by ID
    ---
    tags:
      - Authentication
    parameters:
      - in: path
        name: user_id
        type: integer
        required: true
        description: User ID
    responses:
      200:
        description: User type retrieved successfully
        schema:
        type: object
        properties:
            status:
            type: string
            example: success
            user_id:
            type: integer
            email:
            type: string
            role:
            type: string
            enum: [OWNER, CUSTOMER, EMPLOYEE, ADMIN]
      404:
        description: User not found
        schema:
        $ref: '#/definitions/Error'
      500:
        description: Internal server error
        schema:
        $ref: '#/definitions/Error'
    """
    try:
        # Get the auth user
        user = db.session.scalar(select(AuthUser).where(AuthUser.id == user_id))
        if not user:
            return (
                jsonify(
                    {"status": "error", "message": f"No user found with ID {user_id}"}
                ),
                404,
            )

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
            "address": None,
        }

        # Get role-specific profile information and add to response
        if user.role == "CUSTOMER":
            customer = db.session.scalar(
                select(Customers).where(Customers.user_id == user_id)
            )
            if customer:
                response["profile_id"] = customer.id
                response["first_name"] = customer.first_name
                response["last_name"] = customer.last_name
                response["phone_number"] = customer.phone_number
                response["address"] = customer.address

        elif user.role == "EMPLOYEE":
            employee = db.session.scalar(
                select(Employees).where(Employees.user_id == user_id)
            )
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
            owner = db.session.scalar(
                select(SalonOwners).where(SalonOwners.user_id == user_id)
            )
            if owner:
                response["profile_id"] = owner.id
                response["first_name"] = owner.first_name
                response["last_name"] = owner.last_name
                response["phone_number"] = owner.phone_number
                response["address"] = owner.address

        return jsonify(response), 200

    except Exception as e:
        return (
            jsonify(
                {
                    "status": "error",
                    "message": "Internal server error",
                    "details": str(e),
                }
            ),
            500,
        )


@auth_bp.route("/check-email", methods=["POST"])
def check_email_exists():

    try:
        data = request.get_json(force=True)
        email = data.get("email")

        if not email:
            return jsonify({"status": "error", "message": "Email is required"}), 400

        existing = db.session.scalar(select(AuthUser).where(AuthUser.email == email))

        return jsonify({"exists": bool(existing)}), 200

    except Exception as e:
        return (
            jsonify(
                {
                    "status": "error",
                    "message": "Internal server error",
                    "details": str(e),
                }
            ),
            500,
        )


@auth_bp.route("/forgot-password", methods=["POST"])
def forgot_password():
    """
    Initiate password reset
    ---
    tags:
      - Auth
    summary: Send OTP to user's email
    description: Generates a 6-digit OTP and sends it to the provided email address. If the email does not exist, it returns a success message to prevent user enumeration.
    parameters:
      - in: body
        name: body
        required: true
        description: User email address
        schema:
          type: object
          required:
            - email
          properties:
            email:
              type: string
              format: email
              example: user@example.com
    responses:
      200:
        description: OTP sent successfully (or simulated success)
        schema:
          type: object
          properties:
            message:
              type: string
              example: OTP sent successfully
      500:
        description: Server error or email service failure
    """
    try:
        data = request.get_json()
        email = data.get("email")
        
        user = db.session.query(AuthUser).filter_by(email=email).first()
        
        # Security: Don't reveal if user exists
        if not user:
            return jsonify({"message": "If an account exists, an OTP has been sent."}), 200

        # 1. Generate 6-digit OTP
        otp_code = "".join(random.choices(string.digits, k=6))
        
        # 2. Save to DB with 10 minute expiration
        user.otp_code = otp_code
        user.otp_expires_at = datetime.now() + timedelta(minutes=10)
        db.session.commit()

        # 3. Send Email
        email_service.send_otp_email(user.email, otp_code)
        
        return jsonify({"message": "OTP sent successfully"}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@auth_bp.route("/verify-otp", methods=["POST"])
def verify_otp_route():
    """
    Verify OTP code
    ---
    tags:
      - Auth
    summary: Verify the 6-digit OTP code
    description: Checks if the provided OTP matches the user's stored code and has not expired.
    parameters:
      - in: body
        name: body
        required: true
        description: Email and OTP code
        schema:
          type: object
          required:
            - email
            - otp
          properties:
            email:
              type: string
              format: email
              example: user@example.com
            otp:
              type: string
              example: "123456"
              description: The 6-digit code received via email
    responses:
      200:
        description: OTP verified successfully
        schema:
          type: object
          properties:
            message:
              type: string
              example: OTP verified
            can_reset:
              type: boolean
              example: true
      400:
        description: Invalid OTP, expired OTP, or missing fields
        schema:
          type: object
          properties:
            error:
              type: string
              example: Invalid OTP code
    """
    try:
        data = request.get_json()
        email = data.get("email")
        otp_input = data.get("otp")

        if not email or not otp_input:
             return jsonify({"error": "Email and OTP are required"}), 400

        user = db.session.query(AuthUser).filter_by(email=email).first()
        
        if not user or not user.otp_code:
            return jsonify({"error": "Invalid request"}), 400

        # Check expiration
        if datetime.now() > user.otp_expires_at:
            return jsonify({"error": "OTP has expired"}), 400

        # Check match
        if user.otp_code != otp_input:
            return jsonify({"error": "Invalid OTP code"}), 400

        # Success: Clear OTP so it can't be reused
        user.otp_code = None
        user.otp_expires_at = None
        db.session.commit()
        
        return jsonify({"message": "OTP verified", "can_reset": True}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@auth_bp.route("/reset-password", methods=["POST"])
def reset_password():
    """
    Reset password
    ---
    tags:
      - Auth
    summary: Set a new password
    description: Updates the user's password. This should be called immediately after OTP verification.
    parameters:
      - in: body
        name: body
        required: true
        description: Email and new password
        schema:
          type: object
          required:
            - email
            - password
          properties:
            email:
              type: string
              format: email
              example: user@example.com
            password:
              type: string
              format: password
              example: "NewSecurePass123!"
              description: The new password to set
    responses:
      200:
        description: Password updated successfully
        schema:
          type: object
          properties:
            message:
              type: string
              example: Password updated successfully
      404:
        description: User not found
      500:
        description: Server error
    """
    try:
        data = request.get_json()
        email = data.get("email")
        new_password = data.get("password")
        
        if not email or not new_password:
             return jsonify({"error": "Email and password are required"}), 400

        user = db.session.query(AuthUser).filter_by(email=email).first()
        if not user:
            return jsonify({"error": "User not found"}), 404
            
        hashed_pw = bcrypt.hashpw(new_password.encode("utf-8"), bcrypt.gensalt())
        user.password_hash = hashed_pw
        db.session.commit()
        
        return jsonify({"message": "Password updated successfully"}), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

