from app.api.admin.verification import admin_verification_bp
from app.api.employee.employee_app import employeesapp_bp
from app.api.employee.employee import employees_bp
from app.api.loyalty.customer_loyaltyp import loyalty_bp
from app.api.payments.receipts import receipts_bp
from app.api.payments.methods import payments_bp
from app.api.booking.appointments import appointments_bp
from app.api.salons.reviews import reviews_bp
from app.routes.upload_image_salon import salon_images_bp
from app.routes.salon_register import salon_register_bp
from app.routes.cart import cart_bp
from app.routes.auth import auth_bp
from app.routes.autocomplete import autocomplete_bp
from app.api.employee.employee_pay_portal import employee_payroll_bp
from app.api.customer.user_gallery import user_gallery_bp
from app.api.customer.details import details_bp
from app.routes.salons import salons_bp
from flask import Flask
from flask_cors import CORS
from dotenv import load_dotenv
from flasgger import Swagger
from swagger__config import SWAGGER_CONFIG, SWAGGER_TEMPLATE
import os

load_dotenv()
from app.config import Config  # noqa: E402
from app.extensions import db  # noqa: E402


def create_app():
    print("Starting create_app()")
    app = Flask(__name__)
    print(f"Flask app created: {app}")
    try:
        print("Loading config...")
        app.config.from_object(Config)
        print("Config loaded successfully")
        print(f"Config items: {len(app.config)} items loaded")

        print("Initializing CORS...")
        CORS(app)
        print("CORS initialized")

        print("Initializing database...")
        db.init_app(app)
        print("Database initialized")
        print("Initializing Swagger/OpenAPI documentation...")
        # Determine host based on environment
        host = os.environ.get("API_HOST", "127.0.0.1:5000")
        swagger_template = SWAGGER_TEMPLATE.copy()
        swagger_template["host"] = host

        Swagger(app, config=SWAGGER_CONFIG, template=swagger_template)
        print("Swagger initialized - Access at /api/docs")
        print("Registering blueprints...")

        blueprints = [
            salons_bp,
            autocomplete_bp,
            auth_bp,
            cart_bp,
            salon_register_bp,
            salon_images_bp,
            reviews_bp,
            appointments_bp,
            payments_bp,
            receipts_bp,
            loyalty_bp,
            employees_bp,
            employeesapp_bp,
            employee_payroll_bp,
            admin_verification_bp,
            user_gallery_bp,
            details_bp,
        ]

        for bp in blueprints:
            app.register_blueprint(bp)
            print(f"  ✓ {bp.name} registered")

        print("All blueprints registered successfully")
        print("Adding root route...")

        @app.route("/")
        def home():
            """
            Root endpoint - API status
            ---
            tags:
              - Utility
            responses:
              200:
                description: API is running
                schema:
                  type: object
                  properties:
                    status:
                      type: string
                    message:
                      type: string
                    docs_url:
                      type: string
            """
            try:
                print("Root route accessed")
                return {"status": "ok", "message": "Backend is running!"}, 200
            except Exception as e:
                print(f"Error in root route: {e}")
                import traceback

                traceback.print_exc()
                return {"error": str(e)}, 500

        print("Root route added")

        print("Checking registered routes:")
        route_count = 0
        for rule in app.url_map.iter_rules():
            route_count += 1
            print(
                f"   Route {route_count}: {rule.endpoint} -> {rule.rule} [{list(rule.methods)}]"
            )  # noqa: E501
        print(f"Total routes registered: {route_count}")

    except Exception as e:
        print(f"Error during app creation: {e}")
        print(f"Error type: {type(e)}")
        import traceback

        print(f"Full traceback: {traceback.format_exc()}")
        raise

    print("create_app() completed successfully")
    print(f"Returning app: {app}")
    return app

    # --- Register Blueprints ---


print("About to call create_app()")
app = create_app()
print(f"App created: {app}")
print(f"App name: {app.name}")
print(f"App debug: {app.debug}")

# Port diagnostics
expected_port = os.environ.get("PORT", "NOT SET")
print(f"Railway PORT environment variable: {expected_port}")
print(f"Gunicorn should be listening on: {expected_port}")


if __name__ == "__main__":
    from dotenv import load_dotenv

    # Create a .env contiaining:
    #       MYSQL_PUBLIC_URL= mysql+pymysql://<USER>:<PASSWORD>@<HOST>:<PORT>/salon_app  # noqa: E501
    # OR railway development DB:
    #       MYSQL_PUBLIC_URL= mysql://root:******@mysql.railway.internal:3306/salon_app_dev  # noqa: E501
    #        where ****** ==

    port = int(os.environ.get("PORT", 5000))
    app.run(
        host="0.0.0.0", port=port, debug=os.environ.get("FLASK_ENV") != "production"
    )
# noqa: E402
