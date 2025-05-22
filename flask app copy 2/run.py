# run.py
from app import create_app

app = create_app()
app.secret_key = 'your-secret-key-here'  # Agregar una clave secreta segura

if __name__ == '__main__':
    app.run(debug=True)
