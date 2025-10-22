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
from dotenv import load_dotenv

# (Your existing blueprint imports would be here)
from app.routes.salons import salons_bp 
from app.routes.autocomplete import autocomplete_bp

load_dotenv()

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config) 
    
    CORS(app) 
    
    db.init_app(app)
    
    # (Your existing app.register_blueprint() calls would be here)

    app.register_blueprint(salons_bp)   
    app.register_blueprint(autocomplete_bp) 
    
    return app

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
from app.routes.autocomplete import autocomplete_bp

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config) 
    
    CORS(app) 
    
    db.init_app(app)
    
    # (Your existing app.register_blueprint() calls would be here)

    app.register_blueprint(salons_bp)   
    app.register_blueprint(autocomplete_bp) 
    
    return app

if __name__ == '__main__':
    import os
    from dotenv import load_dotenv

    load_dotenv()  # only needed locally. Create a .env cotaining: MYSQL_PUBLIC_URL= mysql+pymysql://<USER>:<PASSWORD>@<HOST>:<PORT>/salon_app

    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
