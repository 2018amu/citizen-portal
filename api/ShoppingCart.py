from flask import Flask, render_template, session, redirect, url_for, request
from flask_session import Session
from pymongo import MongoClient
import os

# --- Flask App ---
app = Flask(
    __name__,
    static_folder="../static",
    template_folder="../templates"
)
app.secret_key = os.environ.get("FLASK_SECRET", "prod-secret-key")

# --- Flask Session ---
app.config["SESSION_TYPE"] = "filesystem"
app.config["SESSION_FILE_DIR"] = "../flask_session_files"
Session(app)

# --- MongoDB ---
MONGO_URI = os.environ.get(
    "MONGO_URI",
    "mongodb+srv://amushun1992_db_user:PwQge1UbU41Z3Xjs@tm-users.vxuhp3p.mongodb.net/citizen_portal?retryWrites=true&w=majority"
)
client = MongoClient(MONGO_URI)
db = client.get_database()

# --- Routes ---
@app.route("/")
def home():
    return render_template("index.html")

@app.route("/cart")
def cart():
    return render_template("cart.html")

@app.route("/admin")
def admin():
    return render_template("admin.html")

@app.route("/dashboard")
def dashboard():
    return render_template("dashboard.html")

@app.route("/faissadmin")
def faissadmin():
    return render_template("faissadmin.html")

@app.route("/mainfaiss")
def mainfaiss():
    return render_template("mainfaiss.html")

@app.route("/manage")
def manage():
    return render_template("manage.html")

@app.route("/payment")
def payment():
    return render_template("payment.html")

@app.route("/payment_success")
def payment_success():
    return render_template("payment_success.html")

@app.route("/privacy")
def privacy():
    return render_template("privacy.html")

@app.route("/recommendations")
def recommendations():
    return render_template("recommendations.html")

@app.route("/stores")
def stores():
    return render_template("stores.html")

@app.route("/add_to_cart", methods=["POST"])
def add_to_cart():
    product_id = request.form.get("product_id")
    quantity = int(request.form.get("quantity", 1))
    cart = session.get("cart", {})
    cart[product_id] = cart.get(product_id, 0) + quantity
    session["cart"] = cart
    return redirect(url_for("cart"))
