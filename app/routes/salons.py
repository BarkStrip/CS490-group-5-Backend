from flask import Blueprint, jsonify
from app.extensions import db
# Here is where you call the "TABLES" from models. Models is a file that contains all the tables in "Python" format so we can use sqlalchemy
from ..models import Salon, Service, SalonVerify 

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