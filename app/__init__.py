import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from dotenv import load_dotenv
from flask_login import LoginManager

db = SQLAlchemy()
migrate = Migrate()

login_manager = LoginManager()
login_manager.login_view = "auth.login"
login_manager.login_message = None



@login_manager.user_loader
def load_user(user_id):
    from app.models import Usuario
    return Usuario.query.get(int(user_id))

def create_app():

    load_dotenv()

    app = Flask(__name__)

    app.config["SECRET_KEY"] = os.getenv("SECRET_KEY")
    app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("DATABASE_URL")
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False


    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)

    from app import models

    # Blueprints    
    from app.routes.main import  main_bp
    app.register_blueprint(main_bp)

    from app.routes.admin import admin_bp
    app.register_blueprint(admin_bp)

    from app.routes.ponto import ponto_bp
    app.register_blueprint(ponto_bp)

    from app.routes.auth import auth_bp
    app.register_blueprint(auth_bp)

    return app

