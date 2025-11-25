from flask import Blueprint, request, jsonify, current_app
from sqlalchemy import select
import uuid
from app.extensions import db
from app.models import UserImage, Customers
from app.utils.s3_utils import upload_file_to_s3, delete_file_from_s3

user_gallery_bp = Blueprint("user_gallery", __name__, url_prefix="/api/user_gallery")


@user_gallery_bp.route("/upload_image", methods=["POST"])
def upload_customer_image():
    """
    Upload an image to the customer's inspiration gallery
    ---
    tags:
      - User Gallery
    consumes:
      - multipart/form-data
    parameters:
      - in: formData
        name: customer_id
        type: integer
        required: true
        description: The ID of the customer uploading the image
      - in: formData
        name: image_file
        type: file
        required: true
        description: The image file to upload
    responses:
      201:
        description: Image uploaded successfully
        schema:
          type: object
          properties:
            message:
              type: string
              example: Image uploaded successfully
            image:
              type: object
              properties:
                id:
                  type: integer
                customer_id:
                  type: integer
                url:
                  type: string
                created_at:
                  type: string
      400:
        description: Missing required fields or invalid input
        schema:
          $ref: '#/definitions/Error'
      404:
        description: Customer not found
        schema:
          $ref: '#/definitions/Error'
      500:
        description: Internal server error or S3 upload failure
        schema:
          $ref: '#/definitions/Error'
    """
    try:
        customer_id_str = request.form.get("customer_id")
        image_file = request.files.get("image_file")

        if not customer_id_str or not image_file:
            return jsonify({"error": "customer_id and image_file are required"}), 400

        try:
            customer_id = int(customer_id_str)
        except ValueError:
            return jsonify({"error": "customer_id must be a valid integer"}), 400

        customer = db.session.scalar(
            select(Customers).where(Customers.id == customer_id)
        )
        if not customer:
            return jsonify({"error": "Customer not found"}), 404

        bucket_name = current_app.config.get("S3_BUCKET_NAME")
        if not bucket_name:
            return jsonify({"error": "S3_BUCKET_NAME is not configured"}), 500

        unique_name = (
            f"customer_gallery/{customer_id}/{uuid.uuid4()}_{image_file.filename}"
        )

        image_url = upload_file_to_s3(image_file, unique_name, bucket_name)

        if not image_url:
            return jsonify({"error": "File upload failed"}), 500

        new_image = UserImage(customers_id=customer_id, url=image_url)

        db.session.add(new_image)
        db.session.commit()

        return (
            jsonify(
                {
                    "message": "Image uploaded successfully",
                    "image": {
                        "id": new_image.id,
                        "customer_id": new_image.customers_id,
                        "url": new_image.url,
                        "created_at": new_image.created_at,
                    },
                }
            ),
            201,
        )

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": "Failed to upload image", "details": str(e)}), 500


@user_gallery_bp.route("/gallery/<int:customer_id>", methods=["GET"])
def fetch_user_gallery(customer_id):
    """
    Retrieve all inspiration images for a specific customer
    ---
    tags:
      - User Gallery
    parameters:
      - in: path
        name: customer_id
        type: integer
        required: true
        description: The ID of the customer
    responses:
      200:
        description: A list of gallery images
        schema:
          type: object
          properties:
            status:
              type: string
              example: success
            customer_id:
              type: integer
            count:
              type: integer
            gallery:
              type: array
              items:
                type: object
                properties:
                  id:
                    type: integer
                  url:
                    type: string
                  created_at:
                    type: string
      404:
        description: Customer not found
        schema:
          $ref: '#/definitions/Error'
      500:
        description: Internal server error
        schema:
          $ref: '#/definitions/Error'
    """
    try:
        customer = db.session.scalar(
            select(Customers).where(Customers.id == customer_id)
        )
        if not customer:
            return jsonify({"error": "Customer not found"}), 404

        stmt = (
            select(UserImage)
            .where(UserImage.customers_id == customer_id)
            .order_by(UserImage.created_at.desc())
        )
        images = db.session.scalars(stmt).all()

        gallery_data = []
        for img in images:
            gallery_data.append(
                {"id": img.id, "url": img.url, "created_at": img.created_at}
            )

        return (
            jsonify(
                {
                    "status": "success",
                    "customer_id": customer_id,
                    "count": len(gallery_data),
                    "gallery": gallery_data,
                }
            ),
            200,
        )

    except Exception as e:
        return jsonify({"error": "Failed to fetch gallery", "details": str(e)}), 500


@user_gallery_bp.route("/image/<int:image_id>", methods=["DELETE"])
def delete_user_image(image_id):
    """
    Delete a specific image from the user gallery and S3
    ---
    tags:
      - User Gallery
    parameters:
      - in: path
        name: image_id
        type: integer
        required: true
        description: The ID of the image to delete
    responses:
      200:
        description: Image deleted successfully
        schema:
          $ref: '#/definitions/Success'
      404:
        description: Image not found
        schema:
          $ref: '#/definitions/Error'
      500:
        description: Internal server error
        schema:
          $ref: '#/definitions/Error'
    """
    try:
        image_entry = db.session.scalar(
            select(UserImage).where(UserImage.id == image_id)
        )

        if not image_entry:
            return jsonify({"error": "Image not found"}), 404

        bucket_name = current_app.config.get("S3_BUCKET_NAME")

        s3_deleted = delete_file_from_s3(image_entry.url, bucket_name)

        if not s3_deleted:
            print(f"Warning: S3 file deletion failed for {image_entry.url}")

        db.session.delete(image_entry)
        db.session.commit()

        return (
            jsonify({"status": "success", "message": "Image deleted successfully"}),
            200,
        )

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": "Failed to delete image", "details": str(e)}), 500
