from flask import Blueprint, jsonify, request
from app.extensions import db
# Here is where you call the "TABLES" from models. Models is a file that contains all the tables in "Python" format so we can use sqlalchemy
from ..models import Salon, Service, SalonVerify, Review

#math functions to calculate coordinate distance 
from math import radians, sin, cos, sqrt, atan2

from sqlalchemy import func, desc

# Create the Blueprint
salons_bp = Blueprint("salons", __name__, url_prefix="/api/salons")

@salons_bp.route("/cities", methods=["GET"])
def get_cities():
    """
    Fetches a unique list of all cities that have a verified salon.
    """
    try:
        # This query now works because 'SalonVerify' is imported
        city_query = db.session.query(Salon.city)\
                               .filter(Salon.salon_verify.any(SalonVerify.status == 'VERIFIED'))\
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
            db.session.query(Salon)
            .join(SalonVerify, SalonVerify.salon_id == Salon.id)
            .filter(SalonVerify.status == "VERIFIED")
        )

        salons = salons_query.all()

        salon_list = []
        for salon in salons: 
            if hasattr(salon, "latitude") and hasattr(salon, "longitude"): 
                salon_lat = float(salon.latitude)
                salon_long = float(salon.longitude)

                #calculate the distances from the user to the salons 
                if user_lat is not None and user_long is not None: 
                    R = 3958.8                                          # Earth radius in miles
                    dlat = radians(salon_lat - user_lat)
                    dlon = radians(salon_long - user_long)
                    a = sin(dlat / 2) ** 2 + cos(radians(user_lat)) * cos(radians(salon_lat)) * sin(dlon / 2) ** 2
                    c = 2 * atan2(sqrt(a), sqrt(1 - a))
                    distance = R * c
                else: 
                    distance = None
            else: 
                distance = None

            #add top-rated salons that fall within distance to user 
            salon_list.append({
                "id": salon.id,
                "name": salon.name,
                "city": salon.city,
                "latitude": salon.latitude,
                "longitude": salon.longitude,
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
                Salon.type,
                Salon.address, 
                Salon.city,
                Salon.latitude, 
                Salon.longitude,
                Salon.phone, 
                func.avg(Review.rating).label("avg_rating"),
                func.count(Review.id).label("total_reviews")
            )
            .join(SalonVerify, SalonVerify.salon_id == Salon.id)
            .outerjoin(Review, Review.salon_id == Salon.id)
            .filter(SalonVerify.status == "VERIFIED")
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
                "type": salon.type, 
                "address": salon.address,
                "latitude": float(salon.latitude),
                "longitude": float(salon.longitude),
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
                Salon.type,
                Salon.address,
                Salon.city,
                Salon.latitude,
                Salon.longitude,
                func.avg(Review.rating).label("avg_rating"),
                func.count(Review.id).label("total_reviews"),
                func.avg(Service.price).label("avg_service_price")  # NEW: use avg price from services
            )
            .join(SalonVerify, SalonVerify.salon_id == Salon.id)
            .outerjoin(Review, Review.salon_id == Salon.id)
            .outerjoin(Service, Service.salon_id == Salon.id)
            .filter(SalonVerify.status == "VERIFIED")
            .group_by(Salon.id)
        )

        # --- Search keyword (salon name or service) ---
        if q:
            query = query.filter(
                func.lower(Salon.name).like(f"%{q.lower()}%")
                | func.lower(Service.name).like(f"%{q.lower()}%")
            )

        # --- Location (city) filter ---
        if location:
            query = query.filter(func.lower(Salon.city) == location.lower())

        # --- Type filter ---
        if service_type:
            query = query.filter(func.lower(Salon.type) == service_type.lower())

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
                "type": s.type,
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
                Salon.type,
                Salon.address,
                Salon.city,
                Salon.latitude,
                Salon.longitude,
                Salon.phone,
                func.avg(Review.rating).label("avg_rating"),
                func.count(Review.id).label("total_reviews")
            )
            .join(SalonVerify, SalonVerify.salon_id == Salon.id)
            .outerjoin(Review, Review.salon_id == Salon.id)
            .filter(SalonVerify.status == "VERIFIED", Salon.id == salon_id)
            .group_by(
                Salon.id,
                Salon.name,
                Salon.type,
                Salon.address,
                Salon.city,
                Salon.latitude,
                Salon.longitude,
                Salon.phone
            )
            .first()
        )

        if not salon_data:
            return jsonify({"error": "Salon not found"}), 404

        # Build JSON response
        salon_details = {
            "id": salon_data.id,
            "name": salon_data.name,
            "type": salon_data.type,
            "address": salon_data.address,
            "city": salon_data.city,
            "latitude": float(salon_data.latitude) if salon_data.latitude else None,
            "longitude": float(salon_data.longitude) if salon_data.longitude else None,
            "phone": salon_data.phone,
            "avg_rating": round(float(salon_data.avg_rating), 1) if salon_data.avg_rating else None,
            "total_reviews": salon_data.total_reviews,
        }

        return jsonify(salon_details)

    except Exception as e:
        return jsonify({"error": "Database error", "details": str(e)}), 500



@salons_bp.route("/details/<int:salon_id>/reviews", methods=["GET"])
def get_salon_reviews(salon_id):
    """
    Fetch all reviews for a specific salon.
    Works even if the Review table does not include user_name.
    """
    try:
        # --- Detect what columns exist in Review ---
        review_columns = Review.__table__.columns.keys()
        has_user_name = "user_name" in review_columns
        has_user_id = "user_id" in review_columns

        # --- Base Query ---
        reviews_query = (
            db.session.query(
                Review.id,
                Review.rating,
                Review.comment,
                Review.created_at,
                *( [Review.user_name] if has_user_name else [] ),
                *( [Review.user_id] if has_user_id else [] )
            )
            .join(Salon, Review.salon_id == Salon.id)
            .filter(Salon.id == salon_id)
            .order_by(Review.created_at.desc())
        )

        reviews = reviews_query.all()

        # --- Handle no results ---
        if not reviews:
            return jsonify({
                "salon_id": salon_id,
                "reviews_found": 0,
                "reviews": []
            }), 200

        # --- Build JSON safely ---
        review_list = []
        for r in reviews:
            item = {
                "id": r.id,
                "rating": float(r.rating) if r.rating else None,
                "comment": r.comment,
                "created_at": r.created_at.strftime("%Y-%m-%d %H:%M:%S") if r.created_at else None
            }
            if has_user_name:
                item["user_name"] = getattr(r, "user_name", "Anonymous")
            elif has_user_id:
                item["user_id"] = getattr(r, "user_id", None)

            review_list.append(item)

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
