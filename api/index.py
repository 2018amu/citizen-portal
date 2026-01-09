# api/index.py
from ShoppingCartApp import app  # Import the main Flask app

# Vercel expects an object named `app` here
# All your routes are already in ShoppingCart.py
if __name__ == "__main__":
    app.run()