from flask import Blueprint, jsonify, request, current_app
from sqlalchemy import distinct, select
from sqlalchemy.exc import IntegrityError
from app.extensions import db
from ..models import (
    Service, Product, AuthUser, Salon, SalonHours, SalonVerify, 
    SalonOwners, Types
)
from app.utils.s3_utils import upload_file_to_s3
import uuid, os
import bcrypt
import traceback
from datetime import time  

salon_register_bp = Blueprint("salon_register", __name__, url_prefix="/api/salon_register")


@salon_register_bp.route("/register", methods=["POST"])
def register_salon():

    """
    Register a new salon with owner account.
    Creates:
    1. Owner user account (AuthUser, SalonOwners tables)
    2. Salon entry (linked to SalonOwners)
    3. Salon hours (using correct is_open, open_time, close_time)
    4. Initial services
    5. Salon verification entry (status: PENDING)
    """
    
    try:
        data = request.get_json(force=True)
        
        owner_data = data.get("owner", {})
        salon_data = data.get("salon", {})
        hours_data = data.get("hours", {})
        services_data = data.get("services", [])
        terms_agreed = data.get("terms_agreed", False)
        business_confirmed = data.get("business_confirmed", False)
        
        if not owner_data.get("name") or not owner_data.get("email") or not owner_data.get("password"):
            return jsonify({"status": "error", "message": "Owner information incomplete"}), 400
            
        if not salon_data.get("name") or not salon_data.get("type"):
            return jsonify({"status": "error", "message": "Salon information incomplete"}), 400
            
        if not terms_agreed or not business_confirmed:
            return jsonify({"status": "error", "message": "Must agree to terms and confirm business"}), 400
        
        existing = db.session.scalar(select(AuthUser).where(AuthUser.email == owner_data["email"]))
        if existing:
            return jsonify({"status": "error", "message": "Email already registered"}), 409
        

        hashed_pw = bcrypt.hashpw(owner_data["password"].encode("utf-8"), bcrypt.gensalt())
        
        auth_user = AuthUser(
            email=owner_data["email"],
            password_hash=hashed_pw,
            role="OWNER"
        )
        db.session.add(auth_user)
        db.session.flush() 

        name_parts = owner_data["name"].split(' ', 1)
        first_name = name_parts[0]
        last_name = name_parts[1] if len(name_parts) > 1 else ""

        salon_owner = SalonOwners(
            user_id=auth_user.id,
            first_name=first_name,
            last_name=last_name,
            phone_number=owner_data.get("phone")
        )
        db.session.add(salon_owner)
        db.session.flush()
        
        
        type_name = salon_data["type"]
        type_obj = db.session.scalar(select(Types).where(Types.name == type_name))
        if not type_obj:
         
            return jsonify({"status": "error", "message": f"Salon type '{type_name}' not found"}), 400

        full_address = salon_data.get("address", "")
        if salon_data.get("city"):
            full_address += f", {salon_data.get('city')}"
        if salon_data.get("state"):
            full_address += f", {salon_data.get('state')}"
        if salon_data.get("zip"):
            full_address += f" {salon_data.get('zip')}"
        
        salon = Salon(
            salon_owner_id=salon_owner.id,  
            name=salon_data["name"],
            address=full_address.strip(),
            city=salon_data.get("city", ""),
            phone=salon_data.get("phone", ""),
            about="",
            latitude=salon_data.get("latitude", 0.0),   
            longitude=salon_data.get("longitude", 0.0) 
        )
        
        
        db.session.add(salon)
        db.session.flush()  
        
        day_mapping = {
            "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
            "friday": 4, "saturday": 5, "sunday": 6
        }
        
        for day_name, day_num in day_mapping.items():
            is_open = False
            open_time_obj = None
            close_time_obj = None

            if day_name in hours_data and not hours_data[day_name].get("closed"):
                day_hours = hours_data[day_name]
                is_open = True
                try:
                    open_time_obj = time.fromisoformat(day_hours.get("open", "09:00"))
                    close_time_obj = time.fromisoformat(day_hours.get("close", "17:00"))
                except ValueError:
                    return jsonify({"status": "error", "message": f"Invalid time format for {day_name}. Use HH:MM"}), 400
            
            salon_hour = SalonHours(
                salon_id=salon.id,
                weekday=day_num,
                is_open=is_open,
                open_time=open_time_obj,
                close_time=close_time_obj
            )
            db.session.add(salon_hour)
        
        for service_data in services_data:
            if service_data.get("name") and service_data.get("price"):
                service = Service(
                    salon_id=salon.id,
                    name=service_data["name"],
                    price=float(service_data["price"]),
                    duration=int(service_data.get("duration", 60)),
                    is_active=True  
                )
                db.session.add(service)
        
        salon_verify = SalonVerify(
            salon_id=salon.id,
            status="PENDING"
        )
        db.session.add(salon_verify)
        
        db.session.commit()
        
        return jsonify({
            "status": "success",
            "message": "Salon registration submitted for verification",
            "salon_id": salon.id,
            "owner_id": auth_user.id
        }), 201
        
    except IntegrityError as e:
        db.session.rollback()
        return jsonify({
            "status": "error",
            "message": "Database integrity error",
            "details": str(e.orig)
        }), 400
        
    except Exception as e:
        db.session.rollback()
        traceback.print_exc() 
        return jsonify({
            "status": "error",
            "message": "Internal server error",
            "details": str(e)
        }), 500




@salon_register_bp.route("/add_service", methods=["POST"])
def add_service():
    try:
        name = request.form.get("name")
        salon_id_str = request.form.get("salon_id")
        price_str = request.form.get("price", 0)
        duration_str = request.form.get("duration", 0)
        
        is_active_str = request.form.get("is_active", "true") 
        is_active = is_active_str.lower() == "true" 
        
        icon_file = request.files.get("icon_file")
        
        if not name or not salon_id_str:
            return jsonify({"error": "Service name and salon_id are required"}), 400

        try:
            salon_id = int(salon_id_str)
            price = float(price_str)
            duration = int(duration_str)
        except ValueError:
            return jsonify({"error": "salon_id, price, and duration must be valid numbers"}), 400

        existing = db.session.scalar(
            select(Service).where(Service.name == name, Service.salon_id == salon_id)
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

        new_service = Service(
            salon_id=salon_id,
            name=name,
            price=price,
            duration=duration,
            is_active=is_active,  
            icon_url=icon_url
        )

        db.session.add(new_service)
        db.session.commit()

        return jsonify({
            "message": "Service added successfully",
            "service": {
                "id": new_service.id,
                "name": name,
                "price": price,
                "duration": duration,
                "is_active": is_active,
                "icon_url": icon_url
            }
        }), 201

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": "Failed to add service", "details": str(e)}), 500





@salon_register_bp.route("/add_product", methods=["POST"])
def add_product():
    try:
        data = request.form
        icon_file = request.files.get("image_url")
        image_url_from_form = data.get("image_url")

        name = data.get("name")
        salon_id_str = data.get("salon_id")
        price_str = data.get("price", 0)
        stock_qty_str = data.get("stock_qty", 0)
        
        description = data.get("description", "")
        is_active = 1 if str(data.get("is_active", "true")).lower() == "true" else 0
        sku = data.get("sku") or str(uuid.uuid4())[:8]
        
        image_url = None 
        
        if not name or not salon_id_str:
            return jsonify({"error": "Product name and salon_id are required"}), 400
        
        try:
            salon_id = int(salon_id_str)
            price = float(price_str)
            stock_qty = int(stock_qty_str)
        except ValueError:
            return jsonify({"error": "salon_id, price, and stock_qty must be valid numbers"}), 400

        if icon_file:
            unique_name = f"product/{uuid.uuid4()}_{icon_file.filename}"
            bucket_name = current_app.config.get("S3_BUCKET_NAME")
            if not bucket_name:
                return jsonify({"error": "S3_BUCKET_NAME is not configured"}), 500
            image_url = upload_file_to_s3(icon_file, unique_name, bucket_name)
        elif image_url_from_form:
            image_url = image_url_from_form 

        existing = db.session.scalar(
            select(Product).where(Product.name == name, Product.salon_id == salon_id)
        )
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
                "id": new_product.id,
                "salon_id": salon_id,
                "name": name,
                "price": price,
                "stock_qty": stock_qty,
                "description": description,
                "is_active": bool(is_active),
                "sku": sku,
                "image_url": image_url  
            }
        }), 201

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": "Failed to add product", "details": str(e)}), 500




@salon_register_bp.route("/delete_service/<int:service_id>", methods=["DELETE"])
def delete_service(service_id):

    try:
        service = db.session.get(Service, service_id)
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
    try:
        product = db.session.get(Product, product_id)
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