from flask import Blueprint, jsonify, request, current_app
from sqlalchemy import distinct
from app.extensions import db
from ..models import Service, Product
from app.utils.s3_utils import upload_file_to_s3
import uuid, os
import traceback

salon_register_bp = Blueprint("salon_register", __name__, url_prefix="/api/salon_register")

@salon_register_bp.route("/add_service", methods=["POST"])
def add_service():
   
    try:
        # Get form fields
        name = request.form.get("name")
        salon_id = request.form.get("salon_id")
        price = request.form.get("price", 0)
        duration = request.form.get("duration", 0)
        
        is_active_str = request.form.get("is_active", "true") 
        is_active = is_active_str.lower() == "true"
        
        icon_file = request.files.get("icon_file")
        print(icon_file)
        if not name or not salon_id:
            return jsonify({"error": "Service name and salon_id are required"}), 400

        existing = (
            db.session.query(Service)
            .filter(Service.name == name, Service.salon_id == salon_id)
            .first()
        )
        if existing:
            return jsonify({"error": "Service already exists"}), 409
        

        icon_url = None
       

        if icon_file:
         
            
            unique_name = f"services/{uuid.uuid4()}_{icon_file.filename}"
            
            bucket_name = current_app.config.get("S3_BUCKET_NAME")

            if not bucket_name:
     
                return jsonify({"error": "S3_BUCKET_NAME is not configured"}), 500

            icon_url = upload_file_to_s3(icon_file, unique_name, bucket_name)
            
    

        # Create new service entry
        new_service = Service(
            salon_id=salon_id,
            name=name,
            price=price,
            duration=duration,
            is_active="true" if is_active else "false",
            icon_url=icon_url
        )

        db.session.add(new_service)
        db.session.commit()

 

        return jsonify({
            "message": "Service added successfully",
            "service": {
                "name": name,
                "price": price,
                "duration": duration,
                "is_active": is_active, #
                "icon_url": icon_url
            }
        }), 201

    except Exception as e:
        db.session.rollback()
 
        return jsonify({"error": "Failed to add service", "details": str(e)}), 500

@salon_register_bp.route("/add_product", methods=["POST"])
def add_product():
    try:

        # Determine where to get the data from
        if request.is_json:
            data = request.get_json()
        elif request.form:
            data = request.form
        else:
            data = request.args

        # Then read the fields
        name = data.get("name")
        salon_id = data.get("salon_id")
        price = float(data.get("price", 0))
        description = data.get("description", "")
        stock_qty = int(data.get("stock_qty", 0))
        is_active = 1 if str(data.get("is_active", "true")).lower() == "true" else 0
        sku = data.get("sku") or str(uuid.uuid4())[:8]
        icon_file = request.files.get("image_url")
        image_url = data.get("image_url")
        
        if icon_file:
             unique_name = f"product/{uuid.uuid4()}_{icon_file.filename}"
             bucket_name = current_app.config.get("S3_BUCKET_NAME")
        
             if not bucket_name:
                 return jsonify({"error": "S3_BUCKET_NAME is not configured"}), 500
        
             image_url = upload_file_to_s3(icon_file, unique_name, bucket_name)

        if not name or not salon_id:
            return jsonify({"error": "Product name and salon_id are required"}), 400

        existing = db.session.query(Product).filter_by(name=name, salon_id=salon_id).first()
        if existing:
            return jsonify({"error": "Product already exists"}), 409

        new_product = Product(
            salon_id=salon_id,
            name=name,
            price=price,
            stock_qty=stock_qty,
            description=description,
            is_active=is_active,
            sku=sku,
            image_url=image_url  
        )

        db.session.add(new_product)
        db.session.commit()

        return jsonify({
            "message": "Product added successfully",
            "product": {
                "salon_id": salon_id,
                "name": name,
                "price": price,
                "stock_qty": stock_qty,
                "description": description,
                "is_active": is_active,
                "sku": sku,
                "image_url": image_url  
            }
        }), 201

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": "Failed to add product", "details": str(e)}), 500

    except Exception as e:
        db.session.rollback()
        # Print full traceback to console
        print("Exception occurred while adding product:")
        traceback.print_exc()
        # Return the error details in the response
        return jsonify({
            "error": "Failed to add product",
            "details": str(e)
        }), 500


@salon_register_bp.route("/delete_service/<int:service_id>", methods=["DELETE"])
def delete_service(service_id):
    """
    Delete a service by its ID.
    """
    try:
        service = db.session.query(Service).get(service_id)
        if not service:
            return jsonify({"error": f"Service with id {service_id} not found"}), 404

        db.session.delete(service)
        db.session.commit()

        return jsonify({
            "message": f"Service {service_id} deleted successfully"
        }), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({
            "error": "Failed to delete service",
            "details": str(e)
        }), 500


@salon_register_bp.route("/delete_product/<int:product_id>", methods=["DELETE"])
def delete_product(product_id):
    """
    Delete a product by its ID.
    """
    try:
        product = db.session.query(Product).get(product_id)
        if not product:
            return jsonify({"error": f"Product with id {product_id} not found"}), 404

        db.session.delete(product)
        db.session.commit()

        return jsonify({
            "message": f"Product {product_id} deleted successfully"
        }), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({
            "error": "Failed to delete product",
            "details": str(e)
        }), 500
