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
from flask import Flask
from flask_cors import CORS
from app.config import Config
from app.extensions import db

# (Your existing blueprint imports would be here)

from app.routes.salons import salons_bp 



def create_app():
    app = Flask(__name__)
    app.config.from_object(Config) 
    
    CORS(app) 
    
    db.init_app(app)
    
    # (Your existing app.register_blueprint() calls would be here)

    app.register_blueprint(salons_bp)    
    
    return app

if __name__ == "__main__":
    app = create_app()
    app.run(debug=True)