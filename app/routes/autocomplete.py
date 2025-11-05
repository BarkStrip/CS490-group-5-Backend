from flask import Blueprint, jsonify, request
from app.extensions import db
from ..models import Salon, Service, SalonVerify  

autocomplete_bp = Blueprint("autocomplete", __name__, url_prefix="/api")

@autocomplete_bp.route("/autocomplete", methods=["GET"])
def autocomplete_suggestions():
    """
    GET /api/autocomplete
    Purpose: Fast search bar suggestions for Salons and Services.
    Input: ?q=<query_string>&city=<city_name> (city optional)
    
    Behavior:
    - If city is provided:
        → Return salons and services that start with q in that exact city.
    - If city is not provided:
        → Return salons and services that start with q in all cities.
    - If nothing matches, return [].
    """
    query_string = request.args.get('q', default='', type=str).strip()
    city_filter = request.args.get('city', default=None, type=str)
    
    if not query_string:
        return jsonify([])

    search_pattern = f'{query_string}%'
    LIMIT = 10
    suggestions = []

    salon_query = db.session.query(Salon.id, Salon.name)
    
    salon_query = salon_query.filter(
        Salon.salon_verify.any(SalonVerify.status == 'APPROVED')  
    )
    
    if city_filter:
        salon_query = salon_query.filter(Salon.city == city_filter)
    
    salon_query = salon_query.filter(Salon.name.ilike(search_pattern)) \
                             .order_by(Salon.name) \
                             .limit(LIMIT)
    
    salons = [{"id": str(s_id), "name": s_name, "type": "salon"} 
              for s_id, s_name in salon_query.all()]
    suggestions.extend(salons)

    needed = LIMIT - len(suggestions)
    if needed > 0:
        service_query = db.session.query(Service.name)

        service_query = service_query.join(Service.salon).filter(
            Salon.salon_verify.any(SalonVerify.status == 'APPROVED')  
        )

        if city_filter:
            service_query = service_query.filter(Salon.city == city_filter)
        
        service_query = service_query.filter(Service.name.ilike(search_pattern)) \
                                     .distinct() \
                                     .order_by(Service.name) \
                                     .limit(needed)
        
        services = [{"name": row[0], "type": "service"} for row in service_query.all()]
        suggestions.extend(services)

    return jsonify(suggestions)