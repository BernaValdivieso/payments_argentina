import os
import sys

# Add the project root directory to the Python path
current_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, current_dir)

from payment_processor.app import create_app

app = create_app()

if __name__ == "__main__":
    app.run() 