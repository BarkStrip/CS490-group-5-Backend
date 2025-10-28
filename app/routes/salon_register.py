from flask import Blueprint, jsonify, request, current_app
from sqlalchemy import distinct, select
from sqlalchemy.exc import IntegrityError
from app.extensions import db
from ..models import Service, Users, Customers, AuthUser, Salon, SalonHours, SalonVerify
from app.utils.s3_utils import upload_file_to_s3
import uuid, os
import bcrypt
import traceback

salon_register_bp = Blueprint("salon_register", __name__, url_prefix="/api/salon_register")


@salon_register_bp.route("/register", methods=["POST"])
def register_salon():
    """
    Register a new salon with owner account.
    Creates:
    1. Owner user account (Users, Customers, AuthUser tables)
    2. Salon entry
    3. Salon hours
    4. Initial services
    5. Salon verification entry (status: PENDING)
    """
    try:
        data = request.get_json(force=True)
        
        # Extract data
        owner_data = data.get("owner", {})
        salon_data = data.get("salon", {})
        hours_data = data.get("hours", {})
        services_data = data.get("services", [])
        payment_methods = data.get("payment_methods", {})
        terms_agreed = data.get("terms_agreed", False)
        business_confirmed = data.get("business_confirmed", False)
        
        # Validate required fields
        if not owner_data.get("name") or not owner_data.get("email") or not owner_data.get("password"):
            return jsonify({
                "status": "error",
                "message": "Owner information incomplete"
            }), 400
            
        if not salon_data.get("name") or not salon_data.get("type"):
            return jsonify({
                "status": "error",
                "message": "Salon information incomplete"
            }), 400
            
        if not terms_agreed or not business_confirmed:
            return jsonify({
                "status": "error",
                "message": "Must agree to terms and confirm business"
            }), 400
        
        # Check if email already exists
        existing = db.session.scalar(select(AuthUser).where(AuthUser.email == owner_data["email"]))
        if existing:
            return jsonify({
                "status": "error",
                "message": "Email already registered"
            }), 409
        
        # Start transaction
        # 1. Create owner user account
        hashed_pw = bcrypt.hashpw(owner_data["password"].encode("utf-8"), bcrypt.gensalt())
        
        user = Users()
        db.session.add(user)
        db.session.flush()  # Get user.id
        
        # Customers table: id, name, email, phone, role
        customer = Customers(
            name=owner_data["name"],
            email=owner_data["email"],
            phone=owner_data.get("phone"),
            role="OWNER"
        )
        db.session.add(customer)
        db.session.flush()
        
        # AuthUser table: id, email, password_hash, role
        auth_user = AuthUser(
            id=user.id,
            email=owner_data["email"],
            password_hash=hashed_pw,
            role="OWNER"
        )
        db.session.add(auth_user)
        db.session.flush()
        
        # 2. Create salon entry
        # Salon table columns: id, owner_id, name, type, address, city, latitude, longitude, phone, about
        # Note: Your Salon table does NOT have 'state' or 'zip' columns
        # So we combine the full address into the 'address' field
        full_address = salon_data.get("address", "")
        if salon_data.get("city"):
            full_address += f", {salon_data.get('city')}"
        if salon_data.get("state"):
            full_address += f", {salon_data.get('state')}"
        if salon_data.get("zip"):
            full_address += f" {salon_data.get('zip')}"
        
        salon = Salon(
            owner_id=user.id,
            name=salon_data["name"],
            type=salon_data["type"],
            address=full_address.strip(),  # Combined address with city, state, zip
            city=salon_data.get("city", ""),
            phone=salon_data.get("phone", ""),
            about=""  # Empty for now
            # latitude and longitude will be NULL (can be geocoded later)
        )
        db.session.add(salon)
        db.session.flush()  # Get salon.id
        
        # 3. Create salon hours
        # SalonHours table columns: id, salon_id, weekday (1-7), hours (string)
        day_mapping = {
            "monday": 1,
            "tuesday": 2,
            "wednesday": 3,
            "thursday": 4,
            "friday": 5,
            "saturday": 6,
            "sunday": 7
        }
        
        for day_name, day_num in day_mapping.items():
            if day_name in hours_data:
                day_hours = hours_data[day_name]
                if day_hours.get("closed"):
                    hours_str = "Closed"
                else:
                    open_time = day_hours.get("open", "09:00")
                    close_time = day_hours.get("close", "17:00")
                    # Format: "9AM-6PM" to match your database
                    hours_str = f"{open_time}-{close_time}"
                
                salon_hour = SalonHours(
                    salon_id=salon.id,
                    weekday=day_num,
                    hours=hours_str
                )
                db.session.add(salon_hour)
        
        # 4. Create initial services
        # Service table columns: id, salon_id, name, price, duration, is_active, icon_url
        for service_data in services_data:
            if service_data.get("name") and service_data.get("price"):
                service = Service(
                    salon_id=salon.id,
                    name=service_data["name"],
                    price=float(service_data["price"]),
                    duration=int(service_data.get("duration", 60)),
                    is_active="true"  # String "true", not boolean
                    # icon_url will be NULL initially
                )
                db.session.add(service)
        
        # 5. Create salon verification entry (pending approval)
        # SalonVerify table: salon_id, status (PENDING/VERIFIED/REJECTED)
        salon_verify = SalonVerify(
            salon_id=salon.id,
            status="PENDING"
        )
        db.session.add(salon_verify)
        
        # Commit all changes to database
        db.session.commit()
        
        return jsonify({
            "status": "success",
            "message": "Salon registration submitted for verification",
            "salon_id": salon.id,
            "owner_id": user.id
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
        return jsonify({
            "status": "error",
            "message": "Internal server error",
            "details": str(e)
        }), 500

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
        # Service table: id, salon_id, name, price (int), duration (int), is_active (string), icon_url (text)
        new_service = Service(
            salon_id=salon_id,
            name=name,
            price=price,
            duration=duration,
            is_active="true" if is_active else "false",  # String, not boolean
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
