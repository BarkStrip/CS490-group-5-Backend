from flask import Blueprint, jsonify, request, current_app
from app.extensions import db
# Here is where you call the "TABLES" from models. Models is a file that contains all the tables in "Python" format so we can use sqlalchemy
from ..models import Salon, Service, SalonVerify, Review, Customers, Product, Types, t_salon_type_assignments
from app.utils.s3_utils import upload_file_to_s3
import uuid
import traceback

#math functions to calculate coordinate distance 
from math import radians, sin, cos, sqrt, atan2

from sqlalchemy import func, desc, or_
from sqlalchemy.orm import joinedload 
# Create the Blueprint
salons_bp = Blueprint("salons", __name__, url_prefix="/api/salons")


@salons_bp.route("/test", methods=["GET"])
def test_connection():
    """
    Simple test endpoint to verify database connection is working.
    """
    try:
        # Test database connection
        result = db.session.execute(db.text("SELECT 1"))
        return jsonify({"status": "success", "message": "Database connection working"}), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@salons_bp.route("/cities", methods=["GET"])
def get_cities():
    """
    Fetches a unique list of all cities that have a verified salon.
    """
    try:
        # This query now works because 'SalonVerify' is imported
        city_query = db.session.query(Salon.city)\
                               .filter(Salon.salon_verify.any(SalonVerify.status == 'APPROVED'))\
                               .distinct()\
                               .order_by(Salon.city)
        
        cities = [row[0] for row in city_query.all()]
        
        return jsonify({"cities": cities})

    except Exception as e:
        return jsonify({"error": "Database error", "details": str(e)}), 500


@salons_bp.route("/categories", methods=["GET"])
def get_categories():
    """
    Fetches a list of all distinct services .
    """
    try:
        if hasattr(Service, 'icon_url'):
            category_query = db.session.query(
                Service.name, 
                Service.icon_url
            ).distinct().order_by(Service.name)

            categories = [
                {"name": cat.name, "icon_url": cat.icon_url}
                for cat in category_query.all()
            ]
        else:
            category_query = db.session.query(
                Service.name
            ).distinct().order_by(Service.name)
            
            categories = [
                {"name": row[0], "icon_url": None} 
                for row in category_query.all()
            ]
            
        return jsonify({"categories": categories})

    except Exception as e:
        return jsonify({"error": "Database error", "details": str(e)}), 500
    

@salons_bp.route("/top-rated", methods=["GET"])
def getTopRated():
    """
    Fetches top-rated verified salons near the user's location (if provided).
    Sorted by distance ascending and limited to 10 results.
    """
    try: 
        user_lat = request.args.get("user_lat", type = float)       #request user latitude 
        user_long = request.args.get("user_long", type = float)     #request user longitude 

        #search through verified salons 
        salons_query = (
            db.session.query(
                Salon.id,
                Salon.name, 
                func.group_concat(func.distinct(Types.name)).label("salon_types"), 
                Salon.address, 
                Salon.city,
                Salon.latitude, 
                Salon.longitude,
                Salon.phone, 
                func.avg(Review.rating).label("avg_rating"),
                func.count(func.distinct(Review.id)).label("total_reviews") 
            )
            .join(SalonVerify, SalonVerify.salon_id == Salon.id)
            .outerjoin(t_salon_type_assignments, t_salon_type_assignments.c.salon_id == Salon.id)  
            .outerjoin(Types, Types.id == t_salon_type_assignments.c.type_id)                      
            .outerjoin(Review, Review.salon_id == Salon.id)
            .filter(SalonVerify.status == "APPROVED")
            .group_by(Salon.id)
            .order_by(desc("avg_rating"), desc("total_reviews"))
        )

        salons = salons_query.all()

        salon_list = []
        for salon in salons: 
            if salon.latitude and salon.longitude and user_lat is not None and user_long is not None: 
                salon_lat = float(salon.latitude)
                salon_long = float(salon.longitude)

                #calculate the distances from the user to the salons 
                R = 3958.8                                          # Earth radius in miles
                dlat = radians(salon_lat - user_lat)
                dlon = radians(salon_long - user_long)
                a = sin(dlat / 2) ** 2 + cos(radians(user_lat)) * cos(radians(salon_lat)) * sin(dlon / 2) ** 2
                c = 2 * atan2(sqrt(a), sqrt(1 - a))
                distance = R * c
            else: 
                distance = None

            #add top-rated salons that fall within distance to user 
            salon_list.append({
                "id": salon.id,
                "name": salon.name,
                "types": salon.salon_types.split(',') if salon.salon_types else [],  # Convert to array
                "address": salon.address,
                "city": salon.city,
                "latitude": salon.latitude,
                "longitude": salon.longitude,
                "phone": salon.phone,
                "avg_rating": round(float(salon.avg_rating), 2) if salon.avg_rating is not None else None,
                "total_reviews": salon.total_reviews,
                "distance_miles": round(distance, 2) if distance is not None else None
            })

        #sorting by distance 
        if user_lat is not None and user_long is not None: 
            salon_list = [s for s in salon_list if s["distance_miles"] is not None]
            salon_list.sort(key=lambda s: s["distance_miles"])

        top_salons = salon_list[:10]

        return jsonify({"salons": top_salons})
    
    except Exception as e:
        return jsonify({"error": "database error", "details": str(e)}), 500


@salons_bp.route("/generic", methods=["GET"])
def getTopGeneric():
    """
    Fetches top-rated verified salons anywhere (for users who block location).
    Sorted by avg_rating descending and limited to 10 results.
    """
    try: 
        salons_query = (
            db.session.query(
                Salon.id,
                Salon.name, 
                func.group_concat(func.distinct(Types.name)).label("salon_types"), 
                Salon.address, 
                Salon.city,
                Salon.latitude, 
                Salon.longitude,
                Salon.phone, 
                func.avg(Review.rating).label("avg_rating"),
                func.count(func.distinct(Review.id)).label("total_reviews") 
            )
            .join(SalonVerify, SalonVerify.salon_id == Salon.id)
            .outerjoin(t_salon_type_assignments, t_salon_type_assignments.c.salon_id == Salon.id)  
            .outerjoin(Types, Types.id == t_salon_type_assignments.c.type_id)                      
            .outerjoin(Review, Review.salon_id == Salon.id)
            .filter(SalonVerify.status == "APPROVED")
            .group_by(Salon.id)
            .order_by(desc("avg_rating"), desc("total_reviews"))
            .limit(10)                                             
        )

        salons = salons_query.all()

        salons_list = []
        for salon in salons: 
            salons_list.append({
                "id": salon.id,
                "name": salon.name, 
                "types": salon.salon_types.split(',') if salon.salon_types else [],  # Changed from "type" to "types" and split the string
                "address": salon.address,
                "city": salon.city,
                "phone": salon.phone,
                "avg_rating": round(float(salon.avg_rating), 2) if salon.avg_rating is not None else None,
                "total_reviews": salon.total_reviews
            })
        return jsonify({"salons": salons_list})
    
    except Exception as e:
        return jsonify({"error": "database error", "details": str(e)}), 500
    

# -----------------------------------------------------------------------------
# SALON Search ENDPOINT all in one big function
# -----------------------------------------------------------------------------
@salons_bp.route("/search", methods=["GET"])
def search_salons():
    """
    Handles user search queries for salons by name, service, or city.
    Allows filtering by type, rating, and distance.
    Price filtering is applied via the Service table if price data exists there.
    """
    try:
        # --- Query parameters ---
        q = request.args.get("q", type=str)
        location = request.args.get("location", type=str)
        service_type = request.args.get("type", type=str)
        price = request.args.get("price", type=float)  # assume this refers to max price per service
        min_rating = request.args.get("rating", type=float)
        max_distance = request.args.get("distance", type=float)
        user_lat = request.args.get("lat", type=float)
        user_lon = request.args.get("lon", type=float)

        # --- Base Query: Only VERIFIED salons ---
        query = (
            db.session.query(
                Salon.id,
                Salon.name,
                func.group_concat(func.distinct(Types.name)).label("salon_types"),
                Salon.address,
                Salon.city,
                Salon.latitude,
                Salon.longitude,
                func.avg(Review.rating).label("avg_rating"),
                func.count(func.distinct(Review.id)).label("total_reviews"),
                func.avg(Service.price).label("avg_service_price")  # NEW: use avg price from services
            )
            .join(SalonVerify, SalonVerify.salon_id == Salon.id)
            .outerjoin(t_salon_type_assignments, t_salon_type_assignments.c.salon_id == Salon.id)
            .outerjoin(Types, Types.id == t_salon_type_assignments.c.type_id)
            .outerjoin(Review, Review.salon_id == Salon.id)
            .outerjoin(Service, Service.salon_id == Salon.id)
            .filter(SalonVerify.status == "APPROVED")
            .group_by(Salon.id)
        )

        # --- Search keyword (salon name or service) ---
        
        if q:
            query = query.filter(
                func.lower(Salon.name).like(f"{q.lower()}%") | func.lower(Types.name).like(f"{q.lower()}%") 
            )

        #if q:
        #    query = query.filter(
        #        or_(
        #            func.lower(Salon.name).like(f"{q.lower()}%"),
        #           func.lower(Service.name).like(f"{q.lower()}%")
        #        )
        #    )

        # --- Location (city) filter ---
        if location:
            query = query.filter(func.lower(Salon.city) == location.lower())

        # --- Type filter ---
        if service_type:
            type_subquery = (
                db.session.query(t_salon_type_assignments.c.salon_id)
                .join(Types, Types.id == t_salon_type_assignments.c.type_id)
                .filter(func.lower(Types.name) == service_type.lower())
            )
            query = query.filter(Salon.id.in_(type_subquery))

        # --- Price filter (from services) ---
        if price:
            query = query.having(func.avg(Service.price) <= price)

        # --- Rating filter ---
        if min_rating:
            query = query.having(func.avg(Review.rating) >= min_rating)

        salons = query.all()
        salon_list = []

        # --- Distance calculation (if coordinates provided) ---
        for s in salons:
            distance = None
            if user_lat and user_lon and s.latitude and s.longitude:
                R = 3958.8  # Earth radius in miles
                dlat = radians(float(s.latitude) - user_lat)
                dlon = radians(float(s.longitude) - user_lon)
                a = sin(dlat / 2) ** 2 + cos(radians(user_lat)) * cos(radians(float(s.latitude))) * sin(dlon / 2) ** 2
                c = 2 * atan2(sqrt(a), sqrt(1 - a))
                distance = R * c

            # Apply distance filter if requested
            if max_distance and distance and distance > max_distance:
                continue

            salon_list.append({
                "id": s.id,
                "name": s.name,
                "types": s.salon_types.split(',') if s.salon_types else [], 
                "address": s.address,
                "city": s.city,
                "avg_rating": round(float(s.avg_rating), 1) if s.avg_rating else None,
                "total_reviews": s.total_reviews,
                "avg_service_price": round(float(s.avg_service_price), 2) if s.avg_service_price else None,
                "distance_miles": round(distance, 2) if distance else None
            })

        # --- Sort by distance if provided ---
        if user_lat and user_lon:
            salon_list.sort(key=lambda x: (x["distance_miles"] if x["distance_miles"] else 9999))
        else:
            salon_list.sort(key=lambda x: (x["avg_rating"] if x["avg_rating"] else 0), reverse=True)

        return jsonify({"results_found": len(salon_list), "salons": salon_list})

    except Exception as e:
        return jsonify({"error": "Database error", "details": str(e)}), 500


# -----------------------------------------------------------------------------
# SALON DETAILS ENDPOINTS
# -----------------------------------------------------------------------------

@salons_bp.route("/details/<int:salon_id>", methods=["GET"])
def get_salon_details(salon_id):
    """
    Fetch full details for a specific salon.
    Includes basic info, location, contact, and review stats.
    """
    try:
        salon_data = (
            db.session.query(
                Salon.id,
                Salon.name,
                func.group_concat(func.distinct(Types.name)).label("salon_types"), 
                Salon.address,
                Salon.city,
                Salon.latitude,
                Salon.longitude,
                Salon.phone,
                Salon.about,

                func.avg(Review.rating).label("avg_rating"),
                func.count(Review.id).label("total_reviews")
            )
            .join(SalonVerify, SalonVerify.salon_id == Salon.id)
            .outerjoin(t_salon_type_assignments, t_salon_type_assignments.c.salon_id == Salon.id)  
            .outerjoin(Types, Types.id == t_salon_type_assignments.c.type_id)   
            .outerjoin(Review, Review.salon_id == Salon.id)
            .filter(SalonVerify.status == "APPROVED", Salon.id == salon_id)
            .group_by(Salon.id)
            .first()
        )

        if not salon_data:
            return jsonify({"error": "Salon not found"}), 404

        # Build JSON response
        salon_details = {
            "id": salon_data.id,
            "name": salon_data.name,
            "types": salon_data.salon_types.split(',') if salon_data.salon_types else [],
            "address": salon_data.address,
            "city": salon_data.city,
            "latitude": float(salon_data.latitude) if salon_data.latitude else None,
            "longitude": float(salon_data.longitude) if salon_data.longitude else None,
            "phone": salon_data.phone,
            "avg_rating": round(float(salon_data.avg_rating), 1) if salon_data.avg_rating else None,
            "total_reviews": salon_data.total_reviews,
            "about" : salon_data.about
        }

        return jsonify(salon_details)

    except Exception as e:
        return jsonify({"error": "Database error", "details": str(e)}), 500


@salons_bp.route("/details/<int:salon_id>/reviews", methods=["GET"])
def get_salon_reviews(salon_id):

    try:
        reviews_query = (
            db.session.query(
                Review,         
                Customers.first_name,
                Customers.last_name  
            )
            .join(Customers, Review.customers_id == Customers.id) 
            .filter(Review.salon_id == salon_id)
            .options(joinedload(Review.review_image)) 
            .order_by(Review.created_at.desc())
        )

        reviews_with_names = reviews_query.all() 

        if not reviews_with_names:
            return jsonify({
                "salon_id": salon_id,
                "reviews_found": 0,
                "reviews": []
            }), 200

        review_list = []
        for review_obj, customer_first_name, customer_last_name in reviews_with_names:
            
            image_list = [img.url for img in review_obj.review_image]

            review_list.append({
                "id": review_obj.id,
                "rating": float(review_obj.rating) if review_obj.rating else None,
                "comment": review_obj.comment,
                "created_at": review_obj.created_at.strftime("%Y-%m-%d %H:%M:%S") if review_obj.created_at else None,
                "customers_id": review_obj.customers_id,
                "customer_name": f"{customer_first_name} {customer_last_name}",
                "images": image_list 
            })

        return jsonify({
            "salon_id": salon_id,
            "reviews_found": len(review_list),
            "reviews": review_list
        })

    except Exception as e:
        return jsonify({"error": "Database error", "details": str(e)}), 500


@salons_bp.route("/details/<int:salon_id>/services", methods=["GET"])
def get_salon_services(salon_id):
    """
    Fetch all services offered by a specific salon.
    Includes service name, price, duration, and (if available) image/icon.
    """
    try:
        # Detect existing columns in the Service table
        service_columns = Service.__table__.columns.keys()
        has_duration = "duration" in service_columns
        has_image_url = "image_url" in service_columns
        has_icon_url = "icon_url" in service_columns
        has_description = "description" in service_columns

        # --- Query for this salon's services ---
        service_query = (
            db.session.query(Service)
            .filter(Service.salon_id == salon_id)
            .order_by(Service.name.asc())
        )

        services = service_query.all()

        if not services:
            return jsonify({
                "salon_id": salon_id,
                "services_found": 0,
                "services": []
            }), 200

        # --- Build the service list dynamically ---
        service_list = []
        for s in services:
            service_obj = {
                "id": s.id,
                "name": s.name,
                "price": float(s.price) if hasattr(s, "price") and s.price else None,
            }

            if has_duration:
                service_obj["duration"] = getattr(s, "duration", None)

            if has_description:
                service_obj["description"] = getattr(s, "description", None)

            if has_image_url:
                service_obj["image_url"] = getattr(s, "image_url", None)

            if has_icon_url:
                service_obj["icon_url"] = getattr(s, "icon_url", None)

            service_list.append(service_obj)

        return jsonify({
            "salon_id": salon_id,
            "services_found": len(service_list),
            "services": service_list
        })

    except Exception as e:
        return jsonify({"error": "Database error", "details": str(e)}), 500


@salons_bp.route("/details/<int:salon_id>/gallery", methods=["GET"])
def get_salon_gallery(salon_id):
    """
    Fetch all gallery images for a specific salon.
    Uses the SalonImage table.
    Includes image URL and upload timestamps.
    """
    try:
        # Import the correct model
        from app.models import SalonImage

        # --- Query all salon images ---
        images_query = (
            db.session.query(SalonImage)
            .filter(SalonImage.salon_id == salon_id)
            .order_by(SalonImage.created_at.desc())
        )

        images = images_query.all()

        if not images:
            return jsonify({
                "salon_id": salon_id,
                "media_found": 0,
                "gallery": []
            }), 200

        # --- Build JSON response ---
        gallery_list = []
        for img in images:
            gallery_list.append({
                "id": img.id,
                "url": img.url,
                "created_at": img.created_at.strftime("%Y-%m-%d %H:%M:%S") if img.created_at else None,
                "updated_at": img.updated_at.strftime("%Y-%m-%d %H:%M:%S") if img.updated_at else None
            })

        return jsonify({
            "salon_id": salon_id,
            "media_found": len(gallery_list),
            "gallery": gallery_list
        })

    except Exception as e:
        return jsonify({"error": "Database error", "details": str(e)}), 500


@salons_bp.route("/details/<int:salon_id>/products", methods=["GET"])
def get_salon_products(salon_id):
    """
    Fetch all products for a specific salon.
    Uses the Product model as defined (no schema or DB changes).
    """

    try:
        from app.models import Product

        # Fetch all products for this salon (ORM-style)
        products = (
            db.session.query(Product)
            .filter(Product.salon_id == salon_id)
            .order_by(Product.name.asc())
            .all()
        )

        if not products:
            return jsonify({
                "salon_id": salon_id,
                "products_found": 0,
                "products": []
            }), 200

        # Build list dynamically from actual columns
        product_list = []
        for p in products:
            product_list.append({
                "id": p.id,
                "name": p.name,
                "description": p.description,
                "price": float(p.price) if p.price else None,
                "stock_qty": p.stock_qty,
                "is_active": bool(p.is_active),
                "sku": p.sku,
                "image_url": p.image_url,
                "created_at": p.created_at.strftime("%Y-%m-%d %H:%M:%S") if p.created_at else None,
                "updated_at": p.updated_at.strftime("%Y-%m-%d %H:%M:%S") if p.updated_at else None,
            })

        return jsonify({
            "salon_id": salon_id,
            "products_found": len(product_list),
            "products": product_list
        }), 200

    except Exception as e:
        return jsonify({
            "error": "Database error",
            "details": str(e)
        }), 500


