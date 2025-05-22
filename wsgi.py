import os
import sys

# Add the project root directory to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from payment_processor.app import create_app

app = create_app()

if __name__ == "__main__":
    app.run() 