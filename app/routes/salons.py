from flask import Blueprint, jsonify, request
from app.extensions import db

# Here is where you call the "TABLES" from models. Models is a file that
# contains all the tables in "Python" format so we can use sqlalchemy
from ..models import (
    Salon,
    Service,
    SalonVerify,
    Review,
    Customers,
    Types,
    t_salon_type_assignments,
    SalonOwners,
)
from sqlalchemy import select

# math functions to calculate coordinate distance
from math import radians, sin, cos, sqrt, atan2

from sqlalchemy import func, desc
from sqlalchemy.orm import joinedload

# Create the Blueprint
salons_bp = Blueprint("salons", __name__, url_prefix="/api/salons")


@salons_bp.route("/test", methods=["GET"])
def test_connection():
    """
    Test database connection
    ---
    tags:
      - Utility
    responses:
      200:
        description: Database connection is working
        schema:
          type: object
          properties:
            status:
              type: string
              example: success
            message:
              type: string
      500:
        description: Database connection failed
        schema:
          $ref: '#/definitions/Error'
    """
    try:
        # Test database connection
        # result = db.session.execute(db.text("SELECT 1"))
        return (
            jsonify({"status": "success", "message": "Database connection working"}),
            200,
        )
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@salons_bp.route("/cities", methods=["GET"])
def get_cities():
    """
    Get all verified cities with salons
    ---
    tags:
      - Salons
    responses:
      200:
        description: List of cities with verified salons
        schema:
          type: object
          properties:
            cities:
              type: array
              items:
                type: string
              example: ["Newark", "Jersey City", "Hoboken"]
      500:
        description: Database error
        schema:
          $ref: '#/definitions/Error'
    """
    try:
        # This query now works because 'SalonVerify' is imported
        city_query = (
            db.session.query(Salon.city)
            .filter(Salon.salon_verify.any(SalonVerify.status == "APPROVED"))
            .distinct()
            .order_by(Salon.city)
        )

        cities = [row[0] for row in city_query.all()]

        return jsonify({"cities": cities})

    except Exception as e:
        return jsonify({"error": "Database error", "details": str(e)}), 500


@salons_bp.route("/categories", methods=["GET"])
def get_categories():
    """
    Get all service categories
    ---
    tags:
      - Salons
    responses:
      200:
        description: List of distinct service categories
        schema:
          type: object
          properties:
            categories:
              type: array
              items:
                type: object
                properties:
                  name:
                    type: string
                  icon_url:
                    type: string
              example:
                - name: "Haircut"
                  icon_url: "https://s3.amazonaws.com/..."
      500:
        description: Database error
        schema:
          $ref: '#/definitions/Error'
    """
    try:
        if hasattr(Service, "icon_url"):
            category_query = (
                db.session.query(Service.name, Service.icon_url)
                .distinct()
                .order_by(Service.name)
            )

            categories = [
                {"name": cat.name, "icon_url": cat.icon_url}
                for cat in category_query.all()
            ]
        else:
            category_query = (
                db.session.query(Service.name).distinct().order_by(Service.name)
            )

            categories = [
                {"name": row[0], "icon_url": None} for row in category_query.all()
            ]

        return jsonify({"categories": categories})

    except Exception as e:
        return jsonify({"error": "Database error", "details": str(e)}), 500


@salons_bp.route("/top-rated", methods=["GET"])
def getTopRated():
    """
    Get top-rated salons near user location
    ---
    tags:
      - Salons
    parameters:
      - in: query
        name: user_lat
        type: number
        format: float
        description: User latitude
      - in: query
        name: user_long
        type: number
        format: float
        description: User longitude
    responses:
      200:
        description: Top 10 rated salons sorted by distance
        schema:
          type: object
          properties:
            salons:
              type: array
              items:
                $ref: '#/definitions/Salon'
      500:
        description: Database error
        schema:
          $ref: '#/definitions/Error'
    """
    try:
        user_lat = request.args.get("user_lat", type=float)  # request user latitude
        user_long = request.args.get("user_long", type=float)  # request user longitude

        # search through verified salons
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
                func.count(func.distinct(Review.id)).label("total_reviews"),
            )
            .join(SalonVerify, SalonVerify.salon_id == Salon.id)
            .outerjoin(
                t_salon_type_assignments,
                t_salon_type_assignments.c.salon_id == Salon.id,
            )
            .outerjoin(Types, Types.id == t_salon_type_assignments.c.type_id)
            .outerjoin(Review, Review.salon_id == Salon.id)
            .filter(SalonVerify.status == "APPROVED")
            .group_by(Salon.id)
            .order_by(desc("avg_rating"), desc("total_reviews"))
        )

        salons = salons_query.all()

        salon_list = []
        for salon in salons:
            if (
                salon.latitude
                and salon.longitude
                and user_lat is not None
                and user_long is not None
            ):
                salon_lat = float(salon.latitude)
                salon_long = float(salon.longitude)

                # calculate the distances from the user to the salons
                R = 3958.8  # Earth radius in miles
                dlat = radians(salon_lat - user_lat)
                dlon = radians(salon_long - user_long)
                a = (
                    sin(dlat / 2) ** 2
                    + cos(radians(user_lat))
                    * cos(radians(salon_lat))
                    * sin(dlon / 2) ** 2
                )
                c = 2 * atan2(sqrt(a), sqrt(1 - a))
                distance = R * c
            else:
                distance = None

            # add top-rated salons that fall within distance to user
            salon_list.append(
                {
                    "id": salon.id,
                    "name": salon.name,
                    "types": (
                        salon.salon_types.split(",") if salon.salon_types else []
                    ),  # Convert to array
                    "address": salon.address,
                    "city": salon.city,
                    "latitude": salon.latitude,
                    "longitude": salon.longitude,
                    "phone": salon.phone,
                    "avg_rating": (
                        round(float(salon.avg_rating), 2)
                        if salon.avg_rating is not None
                        else None
                    ),
                    "total_reviews": salon.total_reviews,
                    "distance_miles": (
                        round(distance, 2) if distance is not None else None
                    ),
                }
            )

        # sorting by distance
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
    Get top-rated salons (without location filter)
    ---
    tags:
      - Salons
    responses:
      200:
        description: Top 10 rated salons
        schema:
          type: object
          properties:
            salons:
              type: array
              items:
                $ref: '#/definitions/Salon'
      500:
        description: Database error
        schema:
          $ref: '#/definitions/Error'
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
                func.count(func.distinct(Review.id)).label("total_reviews"),
            )
            .join(SalonVerify, SalonVerify.salon_id == Salon.id)
            .outerjoin(
                t_salon_type_assignments,
                t_salon_type_assignments.c.salon_id == Salon.id,
            )
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
            salons_list.append(
                {
                    "id": salon.id,
                    "name": salon.name,
                    "types": (
                        salon.salon_types.split(",") if salon.salon_types else []
                    ),  # Changed from "type" to "types" and split the string
                    "address": salon.address,
                    "city": salon.city,
                    "phone": salon.phone,
                    "avg_rating": (
                        round(float(salon.avg_rating), 2)
                        if salon.avg_rating is not None
                        else None
                    ),
                    "total_reviews": salon.total_reviews,
                }
            )
        return jsonify({"salons": salons_list})

    except Exception as e:
        return jsonify({"error": "database error", "details": str(e)}), 500


# -----------------------------------------------------------------------------
# SALON Search ENDPOINT all in one big function
# -----------------------------------------------------------------------------
@salons_bp.route("/search", methods=["GET"])
def search_salons():
    """
    Search salons by name, service, city, type, rating, price and distance
    ---
    tags:
      - Salons
    parameters:
      - in: query
        name: q
        type: string
        description: Search query (salon name or service type)
      - in: query
        name: location
        type: string
        description: City name filter
      - in: query
        name: type
        type: string
        description: Salon type filter (e.g., Hair, Nails)
      - in: query
        name: price
        type: number
        format: float
        description: Max price per service
      - in: query
        name: rating
        type: number
        format: float
        description: Minimum rating filter
      - in: query
        name: distance
        type: number
        format: float
        description: Max distance in miles
      - in: query
        name: lat
        type: number
        format: float
        description: User latitude
      - in: query
        name: lon
        type: number
        format: float
        description: User longitude
    responses:
      200:
        description: Search results
        schema:
          type: object
          properties:
            results_found:
              type: integer
            salons:
              type: array
              items:
                $ref: '#/definitions/Salon'
      500:
        description: Database error
        schema:
          $ref: '#/definitions/Error'
    """
    try:
        # --- Query parameters ---
        q = request.args.get("q", type=str)
        location = request.args.get("location", type=str)
        service_type = request.args.get("type", type=str)
        price = request.args.get(
            "price", type=float
        )  # assume this refers to max price per service
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
                func.avg(Service.price).label(
                    "avg_service_price"
                ),  # NEW: use avg price from services
            )
            .join(SalonVerify, SalonVerify.salon_id == Salon.id)
            .outerjoin(
                t_salon_type_assignments,
                t_salon_type_assignments.c.salon_id == Salon.id,
            )
            .outerjoin(Types, Types.id == t_salon_type_assignments.c.type_id)
            .outerjoin(Review, Review.salon_id == Salon.id)
            .outerjoin(Service, Service.salon_id == Salon.id)
            .filter(SalonVerify.status == "APPROVED")
            .group_by(Salon.id)
        )

        # --- Search keyword (salon name or service) ---

        if q:
            query = query.filter(
                func.lower(Salon.name).like(f"{q.lower()}%")
                | func.lower(Types.name).like(f"{q.lower()}%")
            )

        # if q:
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
                a = (
                    sin(dlat / 2) ** 2
                    + cos(radians(user_lat))
                    * cos(radians(float(s.latitude)))
                    * sin(dlon / 2) ** 2
                )
                c = 2 * atan2(sqrt(a), sqrt(1 - a))
                distance = R * c

            # Apply distance filter if requested
            if max_distance and distance and distance > max_distance:
                continue

            salon_list.append(
                {
                    "id": s.id,
                    "name": s.name,
                    "types": s.salon_types.split(",") if s.salon_types else [],
                    "address": s.address,
                    "city": s.city,
                    "avg_rating": (
                        round(float(s.avg_rating), 1) if s.avg_rating else None
                    ),
                    "total_reviews": s.total_reviews,
                    "avg_service_price": (
                        round(float(s.avg_service_price), 2)
                        if s.avg_service_price
                        else None
                    ),
                    "distance_miles": round(distance, 2) if distance else None,
                }
            )

        # --- Sort by distance if provided ---
        if user_lat and user_lon:
            salon_list.sort(
                key=lambda x: (x["distance_miles"] if x["distance_miles"] else 9999)
            )
        else:
            salon_list.sort(
                key=lambda x: (x["avg_rating"] if x["avg_rating"] else 0), reverse=True
            )

        return jsonify({"results_found": len(salon_list), "salons": salon_list})

    except Exception as e:
        return jsonify({"error": "Database error", "details": str(e)}), 500


# -----------------------------------------------------------------------------
# SALON DETAILS ENDPOINTS
# -----------------------------------------------------------------------------
@salons_bp.route("/details/<int:salon_id>", methods=["GET"])
def get_salon_details(salon_id):
    """
    Get detailed information about a specific salon
    ---
    tags:
      - Salons
    parameters:
      - in: path
        name: salon_id
        type: integer
        required: true
    responses:
      200:
        description: Salon details retrieved successfully
        schema:
          type: object
          properties:
            id:
              type: integer
            name:
              type: string
            type:
              type: string
            address:
              type: string
            city:
              type: string
            phone:
              type: string
            avg_rating:
              type: number
            total_reviews:
              type: integer
            about:
              type: string
      404:
        description: Salon not found
        schema:
          $ref: '#/definitions/Error'
      500:
        description: Database error
        schema:
          $ref: '#/definitions/Error'
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
                func.count(Review.id).label("total_reviews"),
            )
            .join(SalonVerify, SalonVerify.salon_id == Salon.id)
            .outerjoin(
                t_salon_type_assignments,
                t_salon_type_assignments.c.salon_id == Salon.id,
            )
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
            "types": (
                salon_data.salon_types.split(",") if salon_data.salon_types else []
            ),
            "address": salon_data.address,
            "city": salon_data.city,
            "latitude": float(salon_data.latitude) if salon_data.latitude else None,
            "longitude": float(salon_data.longitude) if salon_data.longitude else None,
            "phone": salon_data.phone,
            "avg_rating": (
                round(float(salon_data.avg_rating), 1)
                if salon_data.avg_rating
                else None
            ),
            "total_reviews": salon_data.total_reviews,
            "about": salon_data.about,
        }

        return jsonify(salon_details)

    except Exception as e:
        return jsonify({"error": "Database error", "details": str(e)}), 500


@salons_bp.route("/details/<int:salon_id>/reviews", methods=["GET"])
def get_salon_reviews(salon_id):
    """
    Get all reviews for a salon
    ---
    tags:
      - Salons
    parameters:
      - in: path
        name: salon_id
        type: integer
        required: true
    responses:
      200:
        description: Reviews retrieved successfully
        schema:
          type: object
          properties:
            salon_id:
              type: integer
            reviews_found:
              type: integer
            reviews:
              type: array
              items:
                $ref: '#/definitions/Review'
      500:
        description: Database error
        schema:
          $ref: '#/definitions/Error'
    """
    try:
        reviews_query = (
            db.session.query(Review, Customers.first_name, Customers.last_name)
            .join(Customers, Review.customers_id == Customers.id)
            .filter(Review.salon_id == salon_id)
            .options(joinedload(Review.review_image))
            .order_by(Review.created_at.desc())
        )

        reviews_with_names = reviews_query.all()

        if not reviews_with_names:
            return (
                jsonify({"salon_id": salon_id, "reviews_found": 0, "reviews": []}),
                200,
            )

        review_list = []
        for review_obj, customer_first_name, customer_last_name in reviews_with_names:

            image_list = [img.url for img in review_obj.review_image]

            review_list.append(
                {
                    "id": review_obj.id,
                    "rating": float(review_obj.rating) if review_obj.rating else None,
                    "comment": review_obj.comment,
                    "created_at": (
                        review_obj.created_at.strftime("%Y-%m-%d %H:%M:%S")
                        if review_obj.created_at
                        else None
                    ),
                    "customers_id": review_obj.customers_id,
                    "customer_name": f"{customer_first_name} {customer_last_name}",
                    "images": image_list,
                }
            )

        return jsonify(
            {
                "salon_id": salon_id,
                "reviews_found": len(review_list),
                "reviews": review_list,
            }
        )

    except Exception as e:
        return jsonify({"error": "Database error", "details": str(e)}), 500


@salons_bp.route("/details/<int:salon_id>/services", methods=["GET"])
def get_salon_services(salon_id):
    """
    Get all services offered by a salon
    ---
    tags:
      - Salons
    parameters:
      - in: path
        name: salon_id
        type: integer
        required: true
    responses:
      200:
        description: Services retrieved successfully
        schema:
          type: object
          properties:
            salon_id:
              type: integer
            services_found:
              type: integer
            services:
              type: array
              items:
                $ref: '#/definitions/Service'
      500:
        description: Database error
        schema:
          $ref: '#/definitions/Error'
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
            return (
                jsonify({"salon_id": salon_id, "services_found": 0, "services": []}),
                200,
            )

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

        return jsonify(
            {
                "salon_id": salon_id,
                "services_found": len(service_list),
                "services": service_list,
            }
        )

    except Exception as e:
        return jsonify({"error": "Database error", "details": str(e)}), 500


@salons_bp.route("/details/<int:salon_id>/gallery", methods=["GET"])
def get_salon_gallery(salon_id):
    """
    Get salon gallery images
    ---
    tags:
      - Salons
    parameters:
      - in: path
        name: salon_id
        type: integer
        required: true
    responses:
      200:
        description: Gallery images retrieved successfully
        schema:
          type: object
          properties:
            salon_id:
              type: integer
            media_found:
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
                  updated_at:
                    type: string
      500:
        description: Database error
        schema:
          $ref: '#/definitions/Error'
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
            return jsonify({"salon_id": salon_id, "media_found": 0, "gallery": []}), 200

        # --- Build JSON response ---
        gallery_list = []
        for img in images:
            gallery_list.append(
                {
                    "id": img.id,
                    "url": img.url,
                    "created_at": (
                        img.created_at.strftime("%Y-%m-%d %H:%M:%S")
                        if img.created_at
                        else None
                    ),
                    "updated_at": (
                        img.updated_at.strftime("%Y-%m-%d %H:%M:%S")
                        if img.updated_at
                        else None
                    ),
                }
            )

        return jsonify(
            {
                "salon_id": salon_id,
                "media_found": len(gallery_list),
                "gallery": gallery_list,
            }
        )

    except Exception as e:
        return jsonify({"error": "Database error", "details": str(e)}), 500


@salons_bp.route("/details/<int:salon_id>/products", methods=["GET"])
def get_salon_products(salon_id):
    """
    Get all products sold by a salon
    ---
    tags:
      - Salons
    parameters:
      - in: path
        name: salon_id
        type: integer
        required: true
    responses:
      200:
        description: Products retrieved successfully
        schema:
          type: object
          properties:
            salon_id:
              type: integer
            products_found:
              type: integer
            products:
              type: array
              items:
                $ref: '#/definitions/Product'
      500:
        description: Database error
        schema:
          $ref: '#/definitions/Error'
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
            return (
                jsonify({"salon_id": salon_id, "products_found": 0, "products": []}),
                200,
            )

        # Build list dynamically from actual columns
        product_list = []
        for p in products:
            product_list.append(
                {
                    "id": p.id,
                    "name": p.name,
                    "description": p.description,
                    "price": float(p.price) if p.price else None,
                    "stock_qty": p.stock_qty,
                    "is_active": bool(p.is_active),
                    "sku": p.sku,
                    "image_url": p.image_url,
                    "created_at": (
                        p.created_at.strftime("%Y-%m-%d %H:%M:%S")
                        if p.created_at
                        else None
                    ),
                    "updated_at": (
                        p.updated_at.strftime("%Y-%m-%d %H:%M:%S")
                        if p.updated_at
                        else None
                    ),
                }
            )

        return (
            jsonify(
                {
                    "salon_id": salon_id,
                    "products_found": len(product_list),
                    "products": product_list,
                }
            ),
            200,
        )

    except Exception as e:
        return jsonify({"error": "Database error", "details": str(e)}), 500


@salons_bp.route("/get_salon/<int:salon_owner_id>", methods=["GET"])
def get_salon(salon_owner_id):

    try:
        owner_stmt = select(SalonOwners).filter_by(id=salon_owner_id)
        owner = db.session.scalar(owner_stmt)

        if not owner:
            return jsonify({"error": "Owner not found"}), 404

        salon_ids = [salon.id for salon in owner.salon]

        if not salon_ids:
            return jsonify({"message": "No salons found for this owner"}), 200

        return jsonify({"salon_owner_id": salon_owner_id, "salon_ids": salon_ids}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@salons_bp.route("/types", methods=["GET"])
def get_types():
    """
    Get all salon types for landing page display
    ---
    tags:
      - Salons
    responses:
      200:
        description: List of all salon types
        schema:
          type: object
          properties:
            types:
              type: array
              items:
                type: object
                properties:
                  id:
                    type: integer
                  name:
                    type: string
              example:
                - id: 1
                  name: "Hair"
                - id: 2
                  name: "Nails"
      500:
        description: Database error
        schema:
          $ref: '#/definitions/Error'
    """
    try:
        types_query = db.session.query(Types.id, Types.name).order_by(Types.name).all()
        
        types_list = [{"id": t.id, "name": t.name} for t in types_query]
        
        return jsonify({"types": types_list}), 200
        
    except Exception as e:
        return jsonify({"error": "Database error", "details": str(e)}), 500


@salons_bp.route("/types/<int:type_id>/salons", methods=["GET"])
def get_salons_by_type(type_id):
    """
    Get all salons that offer a specific type
    ---
    tags:
      - Salons
    parameters:
      - in: path
        name: type_id
        type: integer
        required: true
        description: The type ID to filter by
      - in: query
        name: lat
        type: number
        format: float
        description: User latitude for distance calculation
      - in: query
        name: lon
        type: number
        format: float
        description: User longitude for distance calculation
    responses:
      200:
        description: Salons filtered by type
        schema:
          type: object
          properties:
            type_id:
              type: integer
            type_name:
              type: string
            results_found:
              type: integer
            salons:
              type: array
              items:
                $ref: '#/definitions/Salon'
      404:
        description: Type not found
      500:
        description: Database error
    """
    try:
        user_lat = request.args.get("lat", type=float)
        user_lon = request.args.get("lon", type=float)
        
        # Verify type exists
        type_obj = db.session.query(Types).filter(Types.id == type_id).first()
        if not type_obj:
            return jsonify({"error": "Type not found"}), 404
        
        # Query salons with this type
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
                func.count(func.distinct(Review.id)).label("total_reviews"),
                func.avg(Service.price).label("avg_service_price"),
            )
            .join(SalonVerify, SalonVerify.salon_id == Salon.id)
            .join(
                t_salon_type_assignments,
                t_salon_type_assignments.c.salon_id == Salon.id,
            )
            .join(Types, Types.id == t_salon_type_assignments.c.type_id)
            .outerjoin(Review, Review.salon_id == Salon.id)
            .outerjoin(Service, Service.salon_id == Salon.id)
            .filter(
                SalonVerify.status == "APPROVED",
                t_salon_type_assignments.c.type_id == type_id
            )
            .group_by(Salon.id)
            .order_by(desc("avg_rating"))
        )
        
        salons = salons_query.all()
        
        salon_list = []
        for s in salons:
            distance = None
            if user_lat and user_lon and s.latitude and s.longitude:
                R = 3958.8
                dlat = radians(float(s.latitude) - user_lat)
                dlon = radians(float(s.longitude) - user_lon)
                a = (
                    sin(dlat / 2) ** 2
                    + cos(radians(user_lat))
                    * cos(radians(float(s.latitude)))
                    * sin(dlon / 2) ** 2
                )
                c = 2 * atan2(sqrt(a), sqrt(1 - a))
                distance = R * c
            
            salon_list.append(
                {
                    "id": s.id,
                    "name": s.name,
                    "types": s.salon_types.split(",") if s.salon_types else [],
                    "address": s.address,
                    "city": s.city,
                    "latitude": float(s.latitude) if s.latitude else None,
                    "longitude": float(s.longitude) if s.longitude else None,
                    "phone": s.phone,
                    "avg_rating": (
                        round(float(s.avg_rating), 1) if s.avg_rating else None
                    ),
                    "total_reviews": s.total_reviews,
                    "avg_service_price": (
                        round(float(s.avg_service_price), 2)
                        if s.avg_service_price
                        else None
                    ),
                    "distance_miles": round(distance, 2) if distance else None,
                }
            )
        
        # Sort by distance if coordinates provided
        if user_lat and user_lon:
            salon_list.sort(
                key=lambda x: (x["distance_miles"] if x["distance_miles"] else 9999)
            )
        
        return jsonify(
            {
                "type_id": type_id,
                "type_name": type_obj.name,
                "results_found": len(salon_list),
                "salons": salon_list,
            }
        ), 200
        
    except Exception as e:
        return jsonify({"error": "Database error", "details": str(e)}), 500