import os
import logging
from flask import Flask
from flask_cors import CORS
from flask_compress import Compress
from dotenv import load_dotenv

from .database import init_db
from .limiter import limiter

def create_app():
    load_dotenv()

    app = Flask(__name__)
    Compress(app)
    init_db()

    # CORS
    allowed = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000").split(",")
    CORS(app, resources={r"/*": {"origins": allowed}})

    # Logging
    logging.basicConfig(level=logging.INFO)

    # Лимит запросов
    limiter.init_app(app)

    # Регистрация blueprints
    from .auth import auth_bp
    from .chat import chat_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(chat_bp)

    return app
