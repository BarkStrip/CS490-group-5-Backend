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
        "description": "Complete REST API for salon booking platform with authentication, services, products, reviews, and email notifications",
        "contact": {"email": "support@salonapp.com"},
        "version": "1.0.0",
    },
    "host": "",
    "basePath": "/api",
    "schemes": ["http", "https"],
    "securityDefinitions": {
        "Bearer": {
            "type": "apiKey",
            "name": "Authorization",
            "in": "header",
            "description": 'JWT Authorization header using the Bearer scheme. Example: "Authorization: Bearer {token}"',
        }
    },
    "security": [{"Bearer": []}],
    "tags": [
        {"name": "Authentication", "description": "User authentication endpoints"},
        {"name": "Salons", "description": "Salon search and details"},
        {"name": "Services", "description": "Service management"},
        {"name": "Products", "description": "Product management"},
        {"name": "Cart", "description": "Shopping cart operations"},
        {"name": "Reviews", "description": "Review management"},
        {"name": "Appointments", "description": "Appointment booking and management"},
        {"name": "Notifications", "description": "Email notification system"},
        {"name": "Images", "description": "Image upload and management"},
    ],
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
        "PasswordUpdatePayload": {
            "type": "object",
            "required": ["email", "new_password"],
            "properties": {
                "email": {
                    "type": "string",
                    "format": "email",
                    "example": "customer@example.com",
                },
                "new_password": {"type": "string", "example": "NewSecurePassword123!"},
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
        "Appointment": {
            "type": "object",
            "properties": {
                "id": {"type": "integer"},
                "salon_id": {"type": "integer"},
                "customer_id": {"type": "integer"},
                "employee_id": {"type": "integer"},
                "service_id": {"type": "integer"},
                "start_at": {"type": "string", "format": "date-time"},
                "end_at": {"type": "string", "format": "date-time"},
                "status": {"type": "string", "example": "Booked"},
                "price_at_book": {"type": "number", "format": "float"},
                "notes": {"type": "string"},
            },
        },
        "NotificationTestPayload": {
            "type": "object",
            "required": ["email"],
            "properties": {
                "email": {
                    "type": "string",
                    "format": "email",
                    "example": "test@example.com",
                    "description": "Email address to send test notification to",
                }
            },
        },
        "AppointmentNotificationPayload": {
            "type": "object",
            "required": ["appointment_id"],
            "properties": {
                "appointment_id": {
                    "type": "integer",
                    "example": 123,
                    "description": "ID of the appointment",
                }
            },
        },
        "CancellationNotificationPayload": {
            "type": "object",
            "required": ["appointment_id", "cancelled_by"],
            "properties": {
                "appointment_id": {
                    "type": "integer",
                    "example": 123,
                    "description": "ID of the appointment being cancelled",
                },
                "cancelled_by": {
                    "type": "string",
                    "enum": ["customer", "employee"],
                    "example": "customer",
                    "description": "Who initiated the cancellation",
                },
                "reason": {
                    "type": "string",
                    "example": "Personal emergency",
                    "description": "Optional cancellation reason",
                },
            },
        },
        "AppointmentMessagePayload": {
            "type": "object",
            "required": ["appointment_id", "from_user_type", "message"],
            "properties": {
                "appointment_id": {"type": "integer", "example": 123},
                "from_user_type": {
                    "type": "string",
                    "enum": ["customer", "employee"],
                    "example": "customer",
                    "description": "Who is sending the message",
                },
                "message": {
                    "type": "string",
                    "example": "Can we reschedule to 3pm?",
                    "description": "Message content",
                },
            },
        },
        "ReviewRequestPayload": {
            "type": "object",
            "required": ["customer_id", "salon_id"],
            "properties": {
                "customer_id": {"type": "integer", "example": 123},
                "salon_id": {"type": "integer", "example": 456},
                "service_name": {
                    "type": "string",
                    "example": "Haircut",
                    "description": "Optional service name to include in review request",
                },
            },
        },
        "HoursChangePayload": {
            "type": "object",
            "required": ["salon_id", "new_hours"],
            "properties": {
                "salon_id": {"type": "integer", "example": 123},
                "new_hours": {
                    "type": "object",
                    "example": {
                        "Monday": "9AM-5PM",
                        "Tuesday": "9AM-5PM",
                        "Wednesday": "9AM-6PM",
                        "Thursday": "9AM-6PM",
                        "Friday": "9AM-7PM",
                        "Saturday": "10AM-4PM",
                        "Sunday": "Closed",
                    },
                    "description": "New hours schedule for each day of the week",
                },
            },
        },
        "NotificationSuccessResponse": {
            "type": "object",
            "properties": {
                "status": {"type": "string", "example": "success"},
                "message": {"type": "string", "example": "Email sent successfully"},
                "email_id": {"type": "string", "example": "abc123xyz"},
            },
        },
        "AppointmentCreationResponse": {
            "type": "object",
            "properties": {
                "message": {
                    "type": "string",
                    "example": "Appointment created successfully",
                },
                "appointment_id": {"type": "integer", "example": 123},
                "start_at": {"type": "string", "example": "2025-12-10 14:00:00"},
                "end_at": {"type": "string", "example": "2025-12-10 15:00:00"},
                "status": {"type": "string", "example": "Booked"},
                "photos_count": {"type": "integer", "example": 2},
                "confirmation_email_sent": {"type": "boolean", "example": True},
                "email_error": {"type": "string", "example": None},
            },
        },
    },
    "paths": {
        "/notifications/test": {
            "post": {
                "tags": ["Notifications"],
                "summary": "Test email configuration",
                "description": "Sends a test email to verify Resend integration is working properly",
                "parameters": [
                    {
                        "in": "body",
                        "name": "body",
                        "required": True,
                        "schema": {"$ref": "#/definitions/NotificationTestPayload"},
                    }
                ],
                "responses": {
                    "200": {
                        "description": "Test email sent successfully",
                        "schema": {"$ref": "#/definitions/NotificationSuccessResponse"},
                    },
                    "400": {
                        "description": "Invalid request",
                        "schema": {"$ref": "#/definitions/Error"},
                    },
                    "500": {
                        "description": "Server error",
                        "schema": {"$ref": "#/definitions/Error"},
                    },
                },
            }
        },
        "/notifications/appointment/confirmation": {
            "post": {
                "tags": ["Notifications"],
                "summary": "Send appointment confirmation email",
                "description": "Automatically sends confirmation email after appointment is booked. Called internally by appointment creation endpoint.",
                "parameters": [
                    {
                        "in": "body",
                        "name": "body",
                        "required": True,
                        "schema": {
                            "$ref": "#/definitions/AppointmentNotificationPayload"
                        },
                    }
                ],
                "responses": {
                    "200": {
                        "description": "Confirmation email sent",
                        "schema": {"$ref": "#/definitions/NotificationSuccessResponse"},
                    },
                    "404": {"description": "Appointment not found"},
                    "500": {"description": "Server error"},
                },
            }
        },
        "/notifications/appointment/reminder": {
            "post": {
                "tags": ["Notifications"],
                "summary": "Send appointment reminder",
                "description": "Sends reminder email 1 hour before appointment. Typically triggered by a cron job.",
                "parameters": [
                    {
                        "in": "body",
                        "name": "body",
                        "required": True,
                        "schema": {
                            "$ref": "#/definitions/AppointmentNotificationPayload"
                        },
                    }
                ],
                "responses": {
                    "200": {
                        "description": "Reminder sent successfully",
                        "schema": {"$ref": "#/definitions/NotificationSuccessResponse"},
                    },
                    "404": {"description": "Appointment not found"},
                    "500": {"description": "Server error"},
                },
            }
        },
        "/notifications/appointment/cancel": {
            "post": {
                "tags": ["Notifications"],
                "summary": "Send cancellation notification",
                "description": "Notifies customer or employee about appointment cancellation based on who cancelled",
                "parameters": [
                    {
                        "in": "body",
                        "name": "body",
                        "required": True,
                        "schema": {
                            "$ref": "#/definitions/CancellationNotificationPayload"
                        },
                    }
                ],
                "responses": {
                    "200": {
                        "description": "Cancellation notification sent",
                        "schema": {"$ref": "#/definitions/NotificationSuccessResponse"},
                    },
                    "400": {"description": "Invalid request"},
                    "404": {"description": "Appointment not found"},
                    "500": {"description": "Server error"},
                },
            }
        },
        "/notifications/appointment/message": {
            "post": {
                "tags": ["Notifications"],
                "summary": "Send appointment message",
                "description": "Sends a message between customer and employee about an appointment",
                "parameters": [
                    {
                        "in": "body",
                        "name": "body",
                        "required": True,
                        "schema": {"$ref": "#/definitions/AppointmentMessagePayload"},
                    }
                ],
                "responses": {
                    "200": {
                        "description": "Message sent successfully",
                        "schema": {"$ref": "#/definitions/NotificationSuccessResponse"},
                    },
                    "400": {"description": "Invalid request"},
                    "404": {"description": "Appointment not found"},
                    "500": {"description": "Server error"},
                },
            }
        },
        "/notifications/review-request": {
            "post": {
                "tags": ["Notifications"],
                "summary": "Send review request",
                "description": "Sends review request email after appointment completion with unique review token",
                "parameters": [
                    {
                        "in": "body",
                        "name": "body",
                        "required": True,
                        "schema": {"$ref": "#/definitions/ReviewRequestPayload"},
                    }
                ],
                "responses": {
                    "200": {
                        "description": "Review request sent",
                        "schema": {"$ref": "#/definitions/NotificationSuccessResponse"},
                    },
                    "400": {"description": "Invalid request"},
                    "404": {"description": "Customer or salon not found"},
                    "500": {"description": "Server error"},
                },
            }
        },
        "/notifications/hours-change": {
            "post": {
                "tags": ["Notifications"],
                "summary": "Notify employees about hours change",
                "description": "Sends bulk notification to all active employees about salon hours changes",
                "parameters": [
                    {
                        "in": "body",
                        "name": "body",
                        "required": True,
                        "schema": {"$ref": "#/definitions/HoursChangePayload"},
                    }
                ],
                "responses": {
                    "200": {
                        "description": "Hours change notification sent to all employees",
                        "schema": {
                            "type": "object",
                            "properties": {
                                "status": {"type": "string", "example": "success"},
                                "message": {"type": "string"},
                                "sent_count": {"type": "integer", "example": 5},
                                "total_count": {"type": "integer", "example": 5},
                            },
                        },
                    },
                    "404": {"description": "Salon or employees not found"},
                    "500": {"description": "Server error"},
                },
            }
        },
    },
}
