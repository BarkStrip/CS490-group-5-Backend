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
# -----------------------------------------------------------------------------
# Flask Application Factory (FINAL VERSION — NO FIREBASE)
# -----------------------------------------------------------------------------
from flask import Flask
from flask_cors import CORS
from app.config import Config
from app.extensions import db

# --- Import Blueprints ---
from app.routes.salons import salons_bp
from app.routes.autocomplete import autocomplete_bp
from app.routes.auth import auth_bp
from app.routes.cart import cart_bp


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    # --- Enable CORS ---
    CORS(app)

    # --- Initialize DB ---
    db.init_app(app)

    # --- Register Blueprints ---
    app.register_blueprint(salons_bp)
    app.register_blueprint(autocomplete_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(cart_bp)

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(debug=True)
