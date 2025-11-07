from flask import Blueprint, jsonify, request, current_app
from app.extensions import db
from ..models import Review, ReviewImage ,Customers, Salon
from app.utils.s3_utils import upload_file_to_s3 
import uuid
from sqlalchemy.exc import IntegrityError
reviews_bp = Blueprint("reviews", __name__, url_prefix="/api/reviews")

# -------------------------------------------------------------------------
# POST /api/reviews/post
# Purpose: Create a new review with an optional image upload.
# -------------------------------------------------------------------------
@reviews_bp.route("/postreview", methods=["POST"])
def post_new_review():
    """
    Handles creating a new review.
    Expects multipart/form-data with:
    - customer_id (int)
    - salon_id (int)
    - rating (int)
    - comment (string)
    - picture (file, optional)
    """
    try:

        customer_id = request.form.get("customer_id", type=int)
        salon_id = request.form.get("salon_id", type=int)
        rating = request.form.get("rating", type=int)
        comment = request.form.get("comment")
        
        image_file = request.files.get("picture") 

        if not all([customer_id, salon_id, rating]):
            return jsonify({
                "status": "error",
                "message": "Missing required fields: customer_id, salon_id, rating"
            }), 400

        if not 1 <= rating <= 5:
             return jsonify({
                "status": "error",
                "message": "Rating must be an integer between 1 and 5"
            }), 400

        customer = db.session.get(Customers, customer_id)
        if not customer:
            return jsonify({"status": "error", "message": "Customer not found"}), 404

        salon = db.session.get(Salon, salon_id)
        if not salon:
            return jsonify({"status": "error", "message": "Salon not found"}), 404

        new_review = Review(
            customers_id=customer_id,
            salon_id=salon_id,
            rating=rating,
            comment=comment
        )
        db.session.add(new_review)
        
        db.session.flush() 

        image_url = None
        new_image_id = None

        if image_file:
            bucket_name = current_app.config.get("S3_BUCKET_NAME")
            if not bucket_name:
                current_app.logger.error("S3_BUCKET_NAME is not configured")
                db.session.rollback() 
                return jsonify({"error": "Server configuration error"}), 500

            unique_name = f"reviews/{new_review.id}/{uuid.uuid4()}_{image_file.filename}"
            
            image_url = upload_file_to_s3(image_file, unique_name, bucket_name)
            
            if not image_url:
                db.session.rollback() 
                return jsonify({"error": "File upload failed"}), 500

            new_image = ReviewImage(
                review_id=new_review.id,
                url=image_url
            )
            db.session.add(new_image)
            db.session.flush()
            new_image_id = new_image.id

        db.session.commit()

        return jsonify({
            "status": "success",
            "message": "Review posted successfully",
            "review": {
                "id": new_review.id,
                "customer_id": new_review.customers_id,
                "salon_id": new_review.salon_id,
                "rating": new_review.rating,
                "comment": new_review.comment,
                "created_at": new_review.created_at.isoformat(),
                "image": {
                    "id": new_image_id,
                    "url": image_url
                } if image_url else None
            }
        }), 201

    except IntegrityError as e:
        db.session.rollback()
        current_app.logger.error(f"Review post integrity error: {e}")
        return jsonify({"status": "error", "message": "Database error", "details": str(e.orig)}), 400

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Failed to post review: {e}")
        return jsonify({"status": "error", "message": "Failed to post review", "details": str(e)}), 500

@reviews_bp.route("/rupload_image", methods=["POST"])
def upload_review_image():
    """
    Handles uploading an image for a specific review.
    Expects 'review_id' and 'image_file' in a multipart/form-data request.
    """
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
            current_app.logger.error("S3_BUCKET_NAME is not configured")
            return jsonify({"error": "Server configuration error"}), 500

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
        current_app.logger.error(f"Failed to upload review image: {e}")
        return jsonify({"error": "Failed to upload review image", "details": str(e)}), 500