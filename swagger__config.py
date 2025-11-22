"""
Swagger/OpenAPI configuration for Salon Backend API
"""

SWAGGER_CONFIG = {
    "headers": [],
    "specs": [
        {
            "endpoint": "apispec",
            "route": "/apispec.json",
            "rule_filter": lambda rule: True,
            "model_filter": lambda tag: True,
        }
    ],
    "static_url_path": "/flasgger_static",
    "swagger_ui": True,
    "specs_route": "/api/docs",
}

SWAGGER_TEMPLATE = {
    "swagger": "2.0",
    "info": {
        "title": "Salon Backend API",
        "description": "Complete REST API for salon booking platform with authentication, services, products, and reviews",
        "contact": {"email": "support@salonapp.com"},
        "version": "1.0.0",
    },
    "host": "",
    "basePath": "/api",
    "schemes": ["http"],
    "securityDefinitions": {
        "Bearer": {
            "type": "apiKey",
            "name": "Authorization",
            "in": "header",
            "description": 'JWT Authorization header using the Bearer scheme. Example: "Authorization: Bearer {token}"',
        }
    },
    "security": [{"Bearer": []}],
    "definitions": {
        "Error": {
            "type": "object",
            "properties": {
                "status": {"type": "string", "example": "error"},
                "message": {"type": "string"},
                "details": {"type": "string"},
            },
        },
        "Success": {
            "type": "object",
            "properties": {
                "status": {"type": "string", "example": "success"},
                "message": {"type": "string"},
            },
        },
        "Salon": {
            "type": "object",
            "properties": {
                "id": {"type": "integer"},
                "name": {"type": "string"},
                "type": {"type": "string"},
                "address": {"type": "string"},
                "city": {"type": "string"},
                "latitude": {"type": "number", "format": "float"},
                "longitude": {"type": "number", "format": "float"},
                "phone": {"type": "string"},
                "avg_rating": {"type": "number", "format": "float"},
                "total_reviews": {"type": "integer"},
                "distance_miles": {"type": "number", "format": "float"},
            },
        },
        "Service": {
            "type": "object",
            "properties": {
                "id": {"type": "integer"},
                "name": {"type": "string"},
                "price": {"type": "number", "format": "float"},
                "duration": {"type": "integer"},
                "is_active": {"type": "string"},
                "icon_url": {"type": "string"},
            },
        },
        "Product": {
            "type": "object",
            "properties": {
                "id": {"type": "integer"},
                "name": {"type": "string"},
                "price": {"type": "number", "format": "float"},
                "stock_qty": {"type": "integer"},
                "description": {"type": "string"},
                "is_active": {"type": "integer"},
                "sku": {"type": "string"},
                "image_url": {"type": "string"},
            },
        },
        "Review": {
            "type": "object",
            "properties": {
                "id": {"type": "integer"},
                "rating": {"type": "number", "format": "float"},
                "comment": {"type": "string"},
                "created_at": {"type": "string", "format": "date-time"},
                "customer_name": {"type": "string"},
                "images": {"type": "array", "items": {"type": "string"}},
            },
        },
        "User": {
            "type": "object",
            "properties": {
                "id": {"type": "integer"},
                "name": {"type": "string"},
                "email": {"type": "string", "format": "email"},
                "phone": {"type": "string"},
                "role": {
                    "type": "string",
                    "enum": ["OWNER", "CUSTOMER", "EMPLOYEE", "ADMIN"],
                },
                "gender": {"type": "string"},
            },
        },


        "UserImage": {
            "type": "object",
            "properties": {
                "id": {"type": "integer"},
                "customer_id": {"type": "integer"},
                "url": {"type": "string"},
                "created_at": {"type": "string", "format": "date-time"},
            },
        },
    },
}
