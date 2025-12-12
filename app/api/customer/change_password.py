from flask import Blueprint, request, jsonify
import bcrypt
from ...extensions import db
from ...models import AuthUser

# Create a blueprint for authentication-related routes
update_password = Blueprint("auth_routes", __name__, url_prefix="/api/update_password")


@update_password.route("/password/update", methods=["PUT"])
def update_user_password():
    """
    Update an AuthUser's password by email
    ---
    tags:
      - Authentication
    parameters:
      - in: body
        name: body
        required: true
        schema:
          $ref: '#/definitions/PasswordUpdatePayload'
    responses:
      200:
        description: Password updated successfully
        schema:
          $ref: '#/definitions/Success'
      400:
        description: Invalid request body or missing fields
        schema:
          $ref: '#/definitions/Error'
      404:
        description: User not found
        schema:
          $ref: '#/definitions/Error'
      500:
        description: Server error
        schema:
          $ref: '#/definitions/Error'
    """
    try:
        data = request.get_json(silent=True)
        if not data:
            return (
                jsonify(
                    {
                        "status": "error",
                        "message": "No valid JSON body found. Ensure Content-Type is application/json.",
                    }
                ),
                400,
            )

        email = data.get("email")
        new_password = data.get("new_password")

        if not email or not new_password:
            return (
                jsonify(
                    {
                        "status": "error",
                        "message": "Both 'email' and 'new_password' are required.",
                    }
                ),
                400,
            )

        user = db.session.query(AuthUser).filter_by(email=email).first()

        if not user:
            return (
                jsonify(
                    {
                        "status": "error",
                        "message": f"User with email '{email}' not found.",
                    }
                ),
                404,
            )

        hashed_bytes = bcrypt.hashpw(new_password.encode("utf-8"), bcrypt.gensalt())

        user.password_hash = hashed_bytes

        db.session.commit()

        return (
            jsonify(
                {
                    "status": "success",
                    "message": "Password updated successfully",
                }
            ),
            200,
        )

    except Exception as e:
        db.session.rollback()
        return jsonify({"status": "error", "message": str(e)}), 500
