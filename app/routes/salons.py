from flask import Blueprint, jsonify, request
from app.extensions import db
# Here is where you call the "TABLES" from models. Models is a file that contains all the tables in "Python" format so we can use sqlalchemy
from ..models import Salon, Service, SalonVerify 
from math import radians, sin, cos, sqrt, atan2

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
    

@salons_bp.route("/salons/top-rated", methods=["GET"])
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
                salon_lat = salon.latitude
                salon_long = salon.longitude 

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
