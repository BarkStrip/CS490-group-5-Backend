from flask import Blueprint, jsonify, request, current_app
from app.extensions import db
from ..models import SalonImage, Salon
from app.utils.s3_utils import upload_file_to_s3
from sqlalchemy import select
import uuid

salon_images_bp = Blueprint("salon_images", __name__, url_prefix="/api/salon_images")


@salon_images_bp.route("/upload_salon_image", methods=["POST"])
def upload_salon_image():

    try:
        salon_id_str = request.form.get("salon_id")
        image_file = request.files.get("image_file")

        display_order_str = request.form.get("display_order", "0")

        if not salon_id_str or not image_file:
            return jsonify({"error": "salon_id and image_file are required"}), 400

        try:
            salon_id = int(salon_id_str)
            display_order = int(display_order_str)
        except ValueError:
            return (
                jsonify({"error": "salon_id and display_order must be valid integers"}),
                400,
            )

        bucket_name = current_app.config.get("S3_BUCKET_NAME")
        if not bucket_name:
            return jsonify({"error": "S3_BUCKET_NAME is not configured"}), 500

        unique_name = f"gallery/{salon_id}/{uuid.uuid4()}_{image_file.filename}"

        image_url = upload_file_to_s3(image_file, unique_name, bucket_name)

        if not image_url:
            return jsonify({"error": "File upload failed"}), 500

        new_image = SalonImage(
            salon_id=salon_id, url=image_url, display_order=display_order
        )

        db.session.add(new_image)
        db.session.commit()

        return (
            jsonify(
                {
                    "message": "Image uploaded successfully",
                    "image": {
                        "id": new_image.id,
                        "salon_id": new_image.salon_id,
                        "url": new_image.url,
                        "display_order": new_image.display_order,
                    },
                }
            ),
            201,
        )

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": "Failed to upload image", "details": str(e)}), 500


from flask import Blueprint, jsonify, request, current_app
from app.extensions import db
from ..models import SalonImage, Salon
from app.utils.s3_utils import upload_file_to_s3
from sqlalchemy import select
import uuid

salon_images_bp = Blueprint("salon_images", __name__, url_prefix="/api/salon_images")

@salon_images_bp.route("/upload_salon_home_image", methods=["POST"])
def upload_salon_home_image():
    """
    Upload or update salon home/hero image
    ---
    tags:
      - Salon Images
    parameters:
      - in: formData
        name: image
        type: file
        required: true
        description: Image file to upload
      - in: formData
        name: salon_id
        type: integer
        required: true
        description: ID of the salon
      - in: formData
        name: user_id
        type: integer
        required: true
        description: ID of the user (must be salon owner)
    responses:
      200:
        description: Image uploaded successfully
        schema:
          type: object
          properties:
            message:
              type: string
            image_url:
              type: string
            salon_id:
              type: integer
      400:
        description: Bad request - missing data or unauthorized
      500:
        description: Server error
    """
    try:
        # Get salon_id and user_id from form data
        salon_id = request.form.get('salon_id')
        user_id = request.form.get('user_id')
        
        # Log received values for debugging
        print(f"Received salon_id: {salon_id}, user_id: {user_id}")
        
        if not salon_id or not user_id:
            return jsonify({"error": "salon_id and user_id are required"}), 400
        
        # Validate they can be converted to integers
        try:
            salon_id = int(salon_id)
            user_id = int(user_id)
        except (ValueError, TypeError) as e:
            return jsonify({"error": f"Invalid salon_id or user_id format: {str(e)}"}), 400
        
        # Verify that the user is the salon owner
        salon = db.session.query(Salon).filter(Salon.id == salon_id).first()
        if not salon:
            return jsonify({"error": "Salon not found"}), 404
        
        if salon.salon_owner_id != user_id:
            return jsonify({"error": "Unauthorized: Only the salon owner can upload images"}), 403
        
        # Get the image file
        if 'image' not in request.files:
            return jsonify({"error": "No image file provided"}), 400
        
        file = request.files['image']
        if file.filename == '':
            return jsonify({"error": "No image file selected"}), 400
        
        # Upload to S3
        file_extension = file.filename.rsplit('.', 1)[1].lower() if '.' in file.filename else 'jpg'
        s3_filename = f"salon_hero/{salon_id}/{uuid.uuid4()}.{file_extension}"
        
        image_url = upload_file_to_s3(file, s3_filename)
        
        if not image_url:
            return jsonify({"error": "Failed to upload image to S3"}), 500
        
        # Check if salon already has a hero image (display_order = 0 for hero image)
        existing_image = db.session.query(SalonImage).filter(
            SalonImage.salon_id == salon_id,
            SalonImage.display_order == 0
        ).first()
        
        if existing_image:
            # Update existing hero image
            existing_image.url = image_url
            db.session.commit()
            return jsonify({
                "message": "Salon hero image updated successfully",
                "image_url": image_url,
                "salon_id": salon_id
            }), 200
        else:
            # Create new hero image entry
            new_image = SalonImage(
                salon_id=salon_id,
                url=image_url,
                display_order=0  # 0 = hero/home image
            )
            db.session.add(new_image)
            db.session.commit()
            
            return jsonify({
                "message": "Salon hero image uploaded successfully",
                "image_url": image_url,
                "salon_id": salon_id
            }), 200
            
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": "Server error", "details": str(e)}), 500


@salon_images_bp.route("/get_salon_home_image/<int:salon_id>", methods=["GET"])
def get_salon_home_image(salon_id):
    """
    Get salon home/hero image
    ---
    tags:
      - Salon Images
    parameters:
      - in: path
        name: salon_id
        type: integer
        required: true
        description: ID of the salon
    responses:
      200:
        description: Image URL retrieved successfully
        schema:
          type: object
          properties:
            salon_id:
              type: integer
            image_url:
              type: string
            has_image:
              type: boolean
      404:
        description: Salon not found
      500:
        description: Server error
    """
    try:
        # Get hero image (display_order = 0)
        hero_image = db.session.query(SalonImage).filter(
            SalonImage.salon_id == salon_id,
            SalonImage.display_order == 0
        ).first()
        
        if hero_image:
            return jsonify({
                "salon_id": salon_id,
                "image_url": hero_image.url,
                "has_image": True
            }), 200
        else:
            return jsonify({
                "salon_id": salon_id,
                "image_url": None,
                "has_image": False
            }), 200
            
    except Exception as e:
        return jsonify({"error": "Server error", "details": str(e)}), 500

@salon_images_bp.route("/get_images/<int:salon_id>", methods=["GET"])
def get_salon_images(salon_id):

    try:
        query = (
            select(SalonImage)
            .filter_by(salon_id=salon_id)
            .order_by(SalonImage.display_order.asc(), SalonImage.created_at.desc())
        )
        images = db.session.scalars(query).all()

        if not images:
            return (
                jsonify({"salon_id": salon_id, "images_found": 0, "gallery": []}),
                200,
            )

        gallery_list = []
        for img in images:
            gallery_list.append(
                {
                    "id": img.id,
                    "url": img.url,
                    "display_order": img.display_order,
                    "created_at": (
                        img.created_at.strftime("%Y-%m-%d %H:%M:%S")
                        if img.created_at
                        else None
                    ),
                }
            )

        return (
            jsonify(
                {
                    "salon_id": salon_id,
                    "images_found": len(gallery_list),
                    "gallery": gallery_list,
                }
            ),
            200,
        )

    except Exception as e:
        return jsonify({"error": "Failed to fetch images", "details": str(e)}), 500


