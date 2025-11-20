# Reviews, review images

from flask import Blueprint, jsonify, request, current_app
from app.extensions import db
from ...models import (
    Review,
    ReviewImage,
    ReviewReply,
    SalonOwners,
    Salon,
)
from app.utils.s3_utils import upload_file_to_s3
from sqlalchemy import select
import uuid

reviews_bp = Blueprint("reviews", __name__, url_prefix="/api/reviews")


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

        new_image = ReviewImage(review_id=review_id, url=image_url)

        db.session.add(new_image)
        db.session.commit()

        return (
            jsonify(
                {
                    "message": "Image uploaded successfully",
                    "image": {
                        "id": new_image.id,
                        "review_id": new_image.review_id,
                        "url": new_image.url,
                    },
                }
            ),
            201,
        )

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Failed to upload review image: {e}")
        return (
            jsonify({"error": "Failed to upload review image", "details": str(e)}),
            500,
        )


@reviews_bp.route("/<int:review_id>/reply", methods=["POST"])
def reply_to_review(review_id):
    """
    POST /api/reviews/<review_id>/reply
    Purpose: Allow salon owners to respond to customer reviews.
    Input:
        - review_id (integer) from the URL path
        - JSON body with:
          * text_body (required): The reply text
          * replier_id (required): The ID of the salon owner replying

    Behavior:
    - Check if review exists
    - Verify replier_id owns the salon that received the review
    - Create ReviewReply record
    - Return the created reply with 201 status
    """
    try:
        # Get request body
        data = request.get_json()
        if not data:
            return (
                jsonify(
                    {
                        "error": "Request body required",
                        "message": "JSON body with 'text_body' and 'replier_id' is required",
                    }
                ),
                400,
            )

        replier_id = data.get("replier_id")
        text_body = data.get("text_body")

        if not replier_id:
            return (
                jsonify(
                    {
                        "error": "Missing required field",
                        "message": "replier_id is required",
                    }
                ),
                400,
            )

        # Convert replier_id to integer
        try:
            replier_id = int(replier_id)
        except (ValueError, TypeError):
            return (
                jsonify(
                    {
                        "error": "Invalid value",
                        "message": "replier_id must be an integer",
                    }
                ),
                400,
            )

        if not text_body or not text_body.strip():
            return (
                jsonify(
                    {
                        "error": "Missing required field",
                        "message": "text_body cannot be empty",
                    }
                ),
                400,
            )

        # Get the review
        review = db.session.get(Review, review_id)
        if not review:
            return (
                jsonify(
                    {
                        "error": "Review not found",
                        "message": f"No review found with ID {review_id}",
                    }
                ),
                404,
            )

        # Get the salon and verify ownership
        salon = db.session.get(Salon, review.salon_id)
        if not salon:
            return (
                jsonify(
                    {
                        "error": "Salon not found",
                        "message": f"No salon found with ID {review.salon_id}",
                    }
                ),
                404,
            )

        # Verify replier owns the salon
        salon_owner = db.session.get(SalonOwners, salon.salon_owner_id)
        if not salon_owner:
            return (
                jsonify(
                    {
                        "error": "Unauthorized",
                        "message": "Salon owner profile not found",
                    }
                ),
                403,
            )

        if salon_owner.user_id != replier_id:
            return (
                jsonify(
                    {
                        "error": "Unauthorized",
                        "message": f"Replier ID {replier_id} does not match salon owner user ID {salon_owner.user_id}",
                    }
                ),
                403,
            )

        # Check if reply already exists for this review
        existing_reply = db.session.scalar(
            select(ReviewReply).where(ReviewReply.review_id == review_id)
        )
        if existing_reply:
            return (
                jsonify(
                    {
                        "error": "Reply already exists",
                        "message": "A reply to this review already exists. Use PUT to update it.",
                    }
                ),
                409,
            )

        # Create the reply
        new_reply = ReviewReply(
            review_id=review_id, replier_id=replier_id, text_body=text_body.strip()
        )

        db.session.add(new_reply)
        db.session.commit()

        return (
            jsonify(
                {
                    "status": "success",
                    "message": "Reply created successfully",
                    "reply": {
                        "id": new_reply.id,
                        "review_id": new_reply.review_id,
                        "replier_id": new_reply.replier_id,
                        "text_body": new_reply.text_body,
                        "created_at": (
                            new_reply.created_at.isoformat()
                            if new_reply.created_at
                            else None
                        ),
                        "updated_at": (
                            new_reply.updated_at.isoformat()
                            if new_reply.updated_at
                            else None
                        ),
                    },
                }
            ),
            201,
        )

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Failed to create review reply: {e}")
        return jsonify({"error": "Failed to create reply", "details": str(e)}), 500


@reviews_bp.route("/<int:review_id>/reply", methods=["PUT"])
def update_review_reply(review_id):
    """
    PUT /api/reviews/<review_id>/reply
    Purpose: Allow salon owners to update their reply to a review.
    Input:
        - review_id (integer) from the URL path
        - JSON body with:
          * text_body (required): The updated reply text
          * replier_id (required): The ID of the salon owner updating the reply

    Behavior:
    - Check if review exists
    - Get the existing reply for this review
    - Verify replier_id matches the original replier
    - Update the reply text
    - Return the updated reply with 200 status
    """
    try:
        # Get request body
        data = request.get_json()
        if not data:
            return (
                jsonify(
                    {
                        "error": "Request body required",
                        "message": "JSON body with 'text_body' and 'replier_id' is required",
                    }
                ),
                400,
            )

        replier_id = data.get("replier_id")
        text_body = data.get("text_body")

        if not replier_id:
            return (
                jsonify(
                    {
                        "error": "Missing required field",
                        "message": "replier_id is required",
                    }
                ),
                400,
            )

        # Convert replier_id to integer
        try:
            replier_id = int(replier_id)
        except (ValueError, TypeError):
            return (
                jsonify(
                    {
                        "error": "Invalid value",
                        "message": "replier_id must be an integer",
                    }
                ),
                400,
            )

        if not text_body or not text_body.strip():
            return (
                jsonify(
                    {
                        "error": "Missing required field",
                        "message": "text_body cannot be empty",
                    }
                ),
                400,
            )

        # Get the review
        review = db.session.get(Review, review_id)
        if not review:
            return (
                jsonify(
                    {
                        "error": "Review not found",
                        "message": f"No review found with ID {review_id}",
                    }
                ),
                404,
            )

        # Get the existing reply
        reply = db.session.scalar(
            select(ReviewReply).where(ReviewReply.review_id == review_id)
        )
        if not reply:
            return (
                jsonify(
                    {
                        "error": "Reply not found",
                        "message": f"No reply exists for review {review_id}",
                    }
                ),
                404,
            )

        # Verify the replier_id matches the original replier
        if reply.replier_id != replier_id:
            return (
                jsonify(
                    {
                        "error": "Unauthorized",
                        "message": "You can only update your own reply",
                    }
                ),
                403,
            )

        # Update the reply
        reply.text_body = text_body.strip()
        db.session.commit()

        return (
            jsonify(
                {
                    "status": "success",
                    "message": "Reply updated successfully",
                    "reply": {
                        "id": reply.id,
                        "review_id": reply.review_id,
                        "replier_id": reply.replier_id,
                        "text_body": reply.text_body,
                        "created_at": (
                            reply.created_at.isoformat() if reply.created_at else None
                        ),
                        "updated_at": (
                            reply.updated_at.isoformat() if reply.updated_at else None
                        ),
                    },
                }
            ),
            200,
        )

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Failed to update review reply: {e}")
        return jsonify({"error": "Failed to update reply", "details": str(e)}), 500
