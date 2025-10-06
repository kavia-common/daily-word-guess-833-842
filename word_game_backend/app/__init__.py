from datetime import datetime
import hashlib
import os
from flask import Flask
from flask_cors import CORS
from flask_smorest import Api
from .routes.health import blp as health_blp
from .routes.game import blp as game_blp

# Create Flask app
app = Flask(__name__)
app.url_map.strict_slashes = False

# CORS: allow frontend on localhost:3000
CORS(app, resources={r"/api/*": {"origins": ["http://localhost:3000", "http://127.0.0.1:3000"]}})

# OpenAPI / Swagger configuration
app.config["API_TITLE"] = "Daily Word Game API"
app.config["API_VERSION"] = "v1"
app.config["OPENAPI_VERSION"] = "3.0.3"
app.config["OPENAPI_JSON_PATH"] = "openapi.json"
app.config["OPENAPI_URL_PREFIX"] = "/docs"
app.config["OPENAPI_SWAGGER_UI_PATH"] = ""
app.config["OPENAPI_SWAGGER_UI_URL"] = "https://cdn.jsdelivr.net/npm/swagger-ui-dist/"

# Register blueprints
api = Api(app)
api.register_blueprint(health_blp)
api.register_blueprint(game_blp)

# Default port config note: run.py will start app; use env PORT or default 3001.
