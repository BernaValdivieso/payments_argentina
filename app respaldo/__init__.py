# app/__init__.py

import os
from flask import Flask

def create_app():
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    template_folder = os.path.join(BASE_DIR, '..', 'templates')
    static_folder = os.path.join(BASE_DIR, '..', 'static')

    app = Flask(
        __name__,
        template_folder=template_folder,
        static_folder=static_folder,
        static_url_path='/static'
    )
    
    upload_folder = os.path.join(BASE_DIR, '..', 'uploads')
    processed_folder = os.path.join(BASE_DIR, '..', 'processed')
    
    app.config['UPLOAD_FOLDER'] = upload_folder
    app.config['PROCESSED_FOLDER'] = processed_folder
    
    os.makedirs(upload_folder, exist_ok=True)
    os.makedirs(processed_folder, exist_ok=True)
    
    from .routes import main_bp  # Usando importación relativa
    app.register_blueprint(main_bp)
    
    return app
