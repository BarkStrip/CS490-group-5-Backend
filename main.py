# ----------------------------------------------------------------------------
# Flask Application Factory
# ----------------------------------------------------------------------------
# This file contains the application factory function `create_app()`, which
# is the standard pattern for initializing a scalable Flask application.
#
# PURPOSE:
# 1. Configuration: Loads settings from the `Config` class.
# 2. Extensions: Initializes external services like CORS and the database (db).
# 3. Blueprints: Registers the `salons_bp` blueprint to organize routes.
#
# The main execution block starts the development server when the script is run
# directly.
# ----------------------------------------------------------------------------
from flask import Flask, jsonify
from flask_cors import CORS
from app.config import Config
from app.extensions import db
from dotenv import load_dotenv

# (Your existing blueprint imports would be here)
from app.routes.salons import salons_bp 
from app.routes.autocomplete import autocomplete_bp

load_dotenv()

def create_app():
    print("🚀 Starting create_app()")
    app = Flask(__name__)
    print(f"📱 Flask app created: {app}")
    
    try:
        print("⚙️ Loading config...")
        app.config.from_object(Config)
        print("✓ Config loaded successfully")
        print(f"📊 Config items: {len(app.config)} items loaded")
           
        print("🌐 Initializing CORS...")
        CORS(app)
        print("✓ CORS initialized")
           
        print("🗄️ Initializing database...")
        db.init_app(app)
        print("✓ Database initialized")
           
        print("📋 Registering blueprints...")
        print(f"📋 Salons blueprint: {salons_bp}")
        app.register_blueprint(salons_bp)
        print("✓ Salons blueprint registered")
        
        print(f"📋 Autocomplete blueprint: {autocomplete_bp}")
        app.register_blueprint(autocomplete_bp)
        print("✓ Autocomplete blueprint registered")
        print("✓ Blueprints registered")

        print("🏠 Adding root route...")
        @app.route('/')
        def home():
            print("🏠 ROOT ROUTE WAS CALLED!")
            return jsonify({
                "message": "Jade Backend API is running!",
                "status": "healthy",
                "version": "1.0.0"
            })
        print("✓ Root route added")
        
        print("📍 Checking registered routes:")
        route_count = 0
        for rule in app.url_map.iter_rules():
            route_count += 1
            print(f"  📍 Route {route_count}: {rule.endpoint} -> {rule.rule} [{list(rule.methods)}]")
        
        print(f"✅ Total routes registered: {route_count}")
           
    except Exception as e:
        print(f"❌ Error during app creation: {e}")
        print(f"❌ Error type: {type(e)}")
        import traceback
        print(f"❌ Full traceback: {traceback.format_exc()}")
        raise

    print("🎯 create_app() completed successfully")
    print(f"🎯 Returning app: {app}")
    return app

print("🌟 About to call create_app()")
app = create_app()
print(f"🌟 App created: {app}")
print(f"🌟 App name: {app.name}")
print(f"🌟 App debug: {app.debug}")

# Port diagnostics
import os
expected_port = os.environ.get("PORT", "NOT SET")
print(f"🚪 Railway PORT environment variable: {expected_port}")
print(f"🚪 Gunicorn should be listening on: {expected_port}")

# Check all environment variables related to ports
for key, value in os.environ.items():
    if 'PORT' in key.upper():
        print(f"🚪 {key}: {value}")


if __name__ == '__main__':
    import os
    from dotenv import load_dotenv

    load_dotenv()   # only needed locally. Create a .env contiaining:
                    # MYSQL_PUBLIC_URL= mysql+pymysql://<USER>:<PASSWORD>@<HOST>:<PORT>/salon_app

    port = int(os.environ.get("PORT", 5000))
    #debug = os.environ.get("FLASK_ENV") != "production"
    app.run(host="0.0.0.0", port=port, debug=False)


