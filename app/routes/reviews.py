from flask import Blueprint, jsonify, request, current_app
from app.extensions import db
from ..models import Review, ReviewImage 
from app.utils.s3_utils import upload_file_to_s3
import uuid

reviews_bp = Blueprint("reviews", __name__, url_prefix="/api/reviews")

@reviews_bp.route("/rupload_image", methods=["POST"])
def upload_review_image():

    try:
 
        review_id = request.form.get("review_id")
        image_file = request.files.get("image_file") 

        if not review_id or not image_file:
            return jsonify({"error": "review_id and image_file are required"}), 400
        
   
        review = db.session.get(Review, review_id)
        if not review:
             return jsonify({"error": "Review not found"}), 404
        
 
        bucket_name = current_app.config.get("S3_BUCKET_NAME")
        if not bucket_name:
            return jsonify({"error": "S3_BUCKET_NAME is not configured"}), 500

        unique_name = f"reviews/{review_id}/{uuid.uuid4()}_{image_file.filename}"

        image_url = upload_file_to_s3(image_file, unique_name, bucket_name)
        
        if not image_url:
            return jsonify({"error": "File upload failed"}), 500

        new_image = ReviewImage(
            review_id=review_id,
            url=image_url
        )

        db.session.add(new_image)
        db.session.commit()

        return jsonify({
            "message": "Image uploaded successfully",
            "image": {
                "id": new_image.id,
                "review_id": new_image.review_id,
                "url": new_image.url
            }
        }), 201

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": "Failed to upload review image", "details": str(e)}), 500