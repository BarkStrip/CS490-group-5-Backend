from flask import Blueprint, request, jsonify
from ...extensions import db
from ...models import Salon

salon_details_bp = Blueprint(
    "salon_details", __name__, url_prefix="/api/salons/details"
)


@salon_details_bp.route("/<int:salon_id>", methods=["GET"])
def get_salon_details(salon_id):
    """
    Get salon details by salon ID
    ---
    tags:
      - Salon Details
    parameters:
      - in: path
        name: salon_id
        type: integer
        required: true
        description: Salon ID
    responses:
      200:
        description: Salon details retrieved successfully
        schema:
          type: object
          properties:
            status:
              type: string
              example: success
            data:
              type: object
              properties:
                id:
                  type: integer
                name:
                  type: string
                address:
                  type: string
                city:
                  type: string
                phone:
                  type: string
                latitude:
                  type: number
                longitude:
                  type: number
                about:
                  type: string
      404:
        description: Salon not found
        schema:
          type: object
          properties:
            status:
              type: string
              example: error
            message:
              type: string
    """
    try:
        salon = db.session.get(Salon, salon_id)
        if not salon:
            return jsonify({"status": "error", "message": "Salon not found"}), 404

        return (
            jsonify(
                {
                    "status": "success",
                    "data": {
                        "id": salon.id,
                        "name": salon.name,
                        "address": salon.address,
                        "city": salon.city,
                        "phone": salon.phone,
                        "latitude": float(salon.latitude),
                        "longitude": float(salon.longitude),
                        "about": salon.about,
                    },
                }
            ),
            200,
        )
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@salon_details_bp.route("/<int:salon_id>", methods=["PUT"])
def edit_salon_details(salon_id):
    """
    Edit salon details (name, address, city, phone, latitude, longitude, about)
    ---
    tags:
      - Salon Details
    parameters:
      - in: path
        name: salon_id
        type: integer
        required: true
        description: Salon ID
      - in: body
        name: body
        required: true
        schema:
          type: object
          properties:
            name:
              type: string
              description: Salon name (optional)
            address:
              type: string
              description: Salon address (optional)
            city:
              type: string
              description: Salon city (optional)
            phone:
              type: string
              description: Salon phone number (optional)
            latitude:
              type: number
              description: Salon latitude coordinate (optional)
            longitude:
              type: number
              description: Salon longitude coordinate (optional)
            about:
              type: string
              description: Salon description/about (optional)
    responses:
      200:
        description: Salon details updated successfully
        schema:
          type: object
          properties:
            status:
              type: string
              example: success
            message:
              type: string
            data:
              type: object
              properties:
                id:
                  type: integer
                name:
                  type: string
                address:
                  type: string
                city:
                  type: string
                phone:
                  type: string
                latitude:
                  type: number
                longitude:
                  type: number
                about:
                  type: string
      400:
        description: Invalid request body
        schema:
          type: object
          properties:
            status:
              type: string
              example: error
            message:
              type: string
      404:
        description: Salon not found
        schema:
          type: object
          properties:
            status:
              type: string
              example: error
            message:
              type: string
      500:
        description: Server error
        schema:
          type: object
          properties:
            status:
              type: string
              example: error
            message:
              type: string
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

        salon = db.session.get(Salon, salon_id)
        if not salon:
            return jsonify({"status": "error", "message": "Salon not found"}), 404

        # Update optional fields if provided
        if "name" in data:
            salon.name = data["name"]
        if "address" in data:
            salon.address = data["address"]
        if "city" in data:
            salon.city = data["city"]
        if "phone" in data:
            salon.phone = data["phone"]
        if "latitude" in data:
            salon.latitude = data["latitude"]
        if "longitude" in data:
            salon.longitude = data["longitude"]
        if "about" in data:
            salon.about = data["about"]

        db.session.commit()

        return (
            jsonify(
                {
                    "status": "success",
                    "message": "Salon details updated successfully",
                    "data": {
                        "id": salon.id,
                        "name": salon.name,
                        "address": salon.address,
                        "city": salon.city,
                        "phone": salon.phone,
                        "latitude": float(salon.latitude),
                        "longitude": float(salon.longitude),
                        "about": salon.about,
                    },
                }
            ),
            200,
        )
    except Exception as e:
        db.session.rollback()
        return jsonify({"status": "error", "message": str(e)}), 500
