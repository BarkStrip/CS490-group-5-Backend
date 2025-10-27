from flask import Blueprint, jsonify, request, current_app
from app.extensions import db
from ..models import SalonImage  # Import the SalonImage model
from app.utils.s3_utils import upload_file_to_s3
import uuid, os

salon_images_bp = Blueprint("salon_images", __name__, url_prefix="/api/salon_images")


@salon_images_bp.route("/upload_salon_image", methods=["POST"])
def upload_salon_image():

    try:
        salon_id = request.form.get("salon_id")
        image_file = request.files.get("image_file") 

        if not salon_id or not image_file:
            return jsonify({"error": "salon_id and image_file are required"}), 400
        
        bucket_name = current_app.config.get("S3_BUCKET_NAME")
        if not bucket_name:
            return jsonify({"error": "S3_BUCKET_NAME is not configured"}), 500

        unique_name = f"gallery/{salon_id}/{uuid.uuid4()}_{image_file.filename}"

        image_url = upload_file_to_s3(image_file, unique_name, bucket_name)
        
        if not image_url:
            return jsonify({"error": "File upload failed"}), 500

        new_image = SalonImage(
            salon_id=salon_id,
            url=image_url
        )

        db.session.add(new_image)
        db.session.commit()

        return jsonify({
            "message": "Image uploaded successfully",
            "image": {
                "id": new_image.id,
                "salon_id": new_image.salon_id,
                "url": new_image.url
            }
        }), 201

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": "Failed to upload image", "details": str(e)}), 500
    
@salon_images_bp.route("/get_images/<int:salon_id>", methods=["GET"])
def get_salon_images(salon_id):
    
    try:
        images = (
            db.session.query(SalonImage)
            .filter(SalonImage.salon_id == salon_id)
            .order_by(SalonImage.created_at.desc()) 
            .all()
        )

        if not images:
            return jsonify({
                "salon_id": salon_id,
                "images_found": 0,
                "gallery": []
            }), 200

        gallery_list = []
        for img in images:
            gallery_list.append({
                "id": img.id,
                "url": img.url,
                "created_at": img.created_at.strftime("%Y-%m-%d %H:%M:%S") if img.created_at else None
            })

        return jsonify({
            "salon_id": salon_id,
            "images_found": len(gallery_list),
            "gallery": gallery_list
        }), 200

    except Exception as e:
        return jsonify({"error": "Failed to fetch images", "details": str(e)}), 500

    