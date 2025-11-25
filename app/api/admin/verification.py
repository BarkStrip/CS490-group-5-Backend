# Admin verify salons
from flask import Blueprint, jsonify, request
from app.extensions import db
from app.models import Salon, SalonVerify, Service
from sqlalchemy import func
import traceback

# Create the Blueprint
admin_verification_bp = Blueprint(
    "admin_verification", __name__, url_prefix="/api/admin/verification"
)


@admin_verification_bp.route("", methods=["GET"])
def get_salons_verification():
    """
    GET /api/admin/verification - Get all salons awaiting verification

    ---
    summary: Retrieve unverified salons for admin review
    description: Fetches all salons with specified verification status
    parameters:
      - name: status
        in: query
        type: string
        enum: [PENDING, APPROVED, REJECTED]
        required: false
        description: Filter by verification status (default PENDING)
    responses:
      200:
        description: Returns array of salons with verification details
      500:
        description: Database error
    """
    try:
        # Get query parameters
        status_filter = request.args.get("status", "PENDING")  # Default to PENDING

        # Build base query - removed Salon.type (it's a relationship, not a column)
        query = (
            db.session.query(
                Salon.id,
                Salon.name,
                Salon.address,
                Salon.city,
                Salon.phone,
                Salon.about,
                SalonVerify.status.label("verification_status"),
                SalonVerify.id.label("verification_id"),
                SalonVerify.created_at.label("created_at"),
                SalonVerify.updated_at.label("updated_at"),
                func.count(Service.id).label("service_count"),
            )
            .join(SalonVerify, Salon.id == SalonVerify.salon_id)
            .outerjoin(Service, Salon.id == Service.salon_id)
        )

        # Apply status filter
        if status_filter in ["PENDING", "APPROVED", "REJECTED"]:
            query = query.filter(SalonVerify.status == status_filter)

        # Group by all non-aggregated columns to satisfy ONLY_FULL_GROUP_BY
        query = query.group_by(
            Salon.id,
            Salon.name,
            Salon.address,
            Salon.city,
            Salon.phone,
            Salon.about,
            SalonVerify.status,
            SalonVerify.id,
            SalonVerify.created_at,
            SalonVerify.updated_at,
        )

        # Get all results
        results = query.all()

        # Format response
        salons = []
        for row in results:
            # Fetch salon types separately since it's a many-to-many relationship
            salon_obj = db.session.query(Salon).filter(Salon.id == row.id).first()
            salon_types = (
                [t.name for t in salon_obj.type] if salon_obj and salon_obj.type else []
            )

            salons.append(
                {
                    "id": row.id,
                    "name": row.name,
                    "type": salon_types,
                    "address": row.address,
                    "city": row.city,
                    "phone": row.phone,
                    "about": row.about,
                    "verification_status": row.verification_status,
                    "verification_id": row.verification_id,
                    "created_at": (
                        row.created_at.isoformat() if row.created_at else None
                    ),
                    "updated_at": (
                        row.updated_at.isoformat() if row.updated_at else None
                    ),
                    "service_count": row.service_count or 0,
                }
            )

        return jsonify({"status": "success", "salons": salons}), 200

    except Exception as e:
        traceback.print_exc()
        return (
            jsonify(
                {
                    "status": "error",
                    "message": "Failed to fetch unverified salons",
                    "details": str(e),
                }
            ),
            500,
        )


@admin_verification_bp.route("/<int:verification_id>", methods=["PUT"])
def update_verification_status(verification_id):
    """
    Put /api/admin/verification/<int:verification_id> - Update salon verification status decision
    ---
    summary: Approve or reject a salon registration
    description: Changes verification status (PENDING/APPROVED/REJECTED) and optionally records the admin who made the decision
    parameters:
      - name: verification_id
        in: path
        type: integer
        required: true
        description: The verification record ID to update
    requestBody:
      required: true
      schema:
        type: object
        properties:
          status:
            type: string
            enum: [PENDING, APPROVED, REJECTED]
            description: New verification status (required)
          admin_id:
            type: integer
            description: ID of admin making decision (optional)
        required:
          - status
    responses:
      200:
        description: Status updated successfully - returns updated verification record
      400:
        description: Invalid status value provided
      404:
        description: Verification record not found
      500:
        description: Database error during update
    """
    try:
        data = request.get_json()
        new_status = data.get("status", "").upper()
        admin_id = data.get("admin_id")

        # Validate status
        if new_status not in ["PENDING", "APPROVED", "REJECTED"]:
            return (
                jsonify(
                    {
                        "status": "error",
                        "message": "Invalid status. Must be PENDING, APPROVED, or REJECTED",
                    }
                ),
                400,
            )

        # Find verification record
        verification = (
            db.session.query(SalonVerify)
            .filter(SalonVerify.id == verification_id)
            .first()
        )

        if not verification:
            return (
                jsonify(
                    {"status": "error", "message": "Verification record not found"}
                ),
                404,
            )

        # Update verification
        verification.status = new_status
        if admin_id:
            verification.admin_id = admin_id

        db.session.commit()

        return (
            jsonify(
                {
                    "status": "success",
                    "message": f"Verification status updated to {new_status}",
                    "verification": {
                        "id": verification.id,
                        "salon_id": verification.salon_id,
                        "status": verification.status,
                        "admin_id": verification.admin_id,
                        "updated_at": (
                            verification.updated_at.isoformat()
                            if verification.updated_at
                            else None
                        ),
                    },
                }
            ),
            200,
        )

    except Exception as e:
        db.session.rollback()
        traceback.print_exc()
        return (
            jsonify(
                {
                    "status": "error",
                    "message": "Failed to update verification status",
                    "details": str(e),
                }
            ),
            500,
        )
