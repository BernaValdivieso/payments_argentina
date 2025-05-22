from flask import Flask
import os

def create_app():
    template_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'templates')
    app = Flask(__name__, template_folder=template_dir)
    app.config['SECRET_KEY'] = 'dev-key-123'
    app.config['UPLOAD_FOLDER'] = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'uploads')
    app.config['PROCESSED_FOLDER'] = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'processed')
    
    # Ensure upload and processed directories exist
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    os.makedirs(app.config['PROCESSED_FOLDER'], exist_ok=True)
    
    from .routes import main
    app.register_blueprint(main)
    
    return app 