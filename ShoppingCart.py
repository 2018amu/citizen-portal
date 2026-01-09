import os
import io
import csv
import json
import bcrypt
import logging
from datetime import datetime, timedelta
from functools import wraps

from flask import (
    Flask, request, jsonify, render_template,
    session, redirect, url_for, send_file
)
from flask_cors import CORS
from pymongo import MongoClient
from bson import ObjectId, Binary, json_util

# ================================
# CONFIG
# ================================
MONGO_URI = os.environ.get(
    "MONGO_URI",
    "mongodb+srv://amushun1992_db_user:PwQge1UbU41Z3Xjs@tm-users.vxuhp3p.mongodb.net/citizen_portal?retryWrites=true&w=majority",
)

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")

app_secret = os.environ.get("FLASK_SECRET", "prod-secret-key")


if not MONGO_URI:
    raise RuntimeError("MONGO_URI environment variable not set")

# ================================
# APP
# ================================
app = Flask(__name__, static_folder="static", template_folder="templates")
app.secret_key = app_secret
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=True,
)
CORS(app, supports_credentials=True)

logging.basicConfig(level=logging.INFO)
logger = app.logger

# ================================
# DATABASE
# ================================
client = MongoClient(MONGO_URI)
db = client["citizen_portal"]

services_col = db["services"]
categories_col = db["categories"]
officers_col = db["officers"]
ads_col = db["ads"]
admins_col = db["admins"]
eng_col = db["engagements"]
profiles_col = db["profiles"]
newusers_col = db["webusers"]
products_col = db["products"]
orders_col = db["orders"]
payments_col = db["payments"]

# ================================
# UTILITIES
# ================================
def to_jsonable(obj):
    return json.loads(json_util.dumps(obj))

def admin_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not session.get("admin_logged_in"):
            return redirect(url_for("admin_login"))
        return fn(*args, **kwargs)
    return wrapper

# ================================
# HOME
# ================================
@app.route("/")
def home():
    return "Citizen Portal API running"

# ================================
# DASHBOARD
# ================================
@app.route("/dashboard")
def dashboard():
    now = datetime.utcnow()
    analytics = {
        "users": newusers_col.count_documents({}),
        "orders": orders_col.count_documents({}),
        "revenue": sum(p.get("amount", 0) for p in payments_col.find({"status": "completed"})),
        "recent_engagements": to_jsonable(
            eng_col.find().sort("timestamp", -1).limit(10)
        )
    }
    return render_template("dashboard.html", analytics=analytics)

# ================================
# STORE APIs
# ================================
@app.route("/api/store/products")
def products():
    query = {}
    if request.args.get("category"):
        query["category"] = request.args["category"]
    products = list(products_col.find(query))
    return jsonify(to_jsonable(products))

@app.route("/api/store/order", methods=["POST"])
def create_order():
    payload = request.json or {}
    order_id = f"ORD{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"

    order = {
        "order_id": order_id,
        "user_id": payload.get("user_id"),
        "items": payload.get("items", []),
        "total_amount": payload.get("total_amount", 0),
        "status": "pending",
        "created": datetime.utcnow()
    }
    orders_col.insert_one(order)

    if payload.get("payment_method", "").lower() == "cod":
        payments_col.insert_one({
            "payment_id": f"PAY{datetime.utcnow().strftime('%Y%m%d%H%M%S')}",
            "order_id": order_id,
            "amount": order["total_amount"],
            "status": "completed",
            "created": datetime.utcnow()
        })
        orders_col.update_one({"order_id": order_id}, {"$set": {"status": "paid"}})

    return jsonify({"success": True, "order_id": order_id})

# ================================
# ENGAGEMENT
# ================================
@app.route("/api/engagement", methods=["POST"])
def log_engagement():
    data = request.json or {}
    data["timestamp"] = datetime.utcnow()
    eng_col.insert_one(data)
    return jsonify({"ok": True})

@app.route("/api/engagement/list", methods=["GET"])
def list_engagements():
    return jsonify(to_jsonable(list(eng_col.find())))

# ================================
# PROFILE
# ================================
@app.route("/api/profile/create", methods=["POST"])
def create_profile():
    payload = request.json or {}
    doc = {
        "name": payload.get("name"),
        "email": payload.get("email"),
        "created": datetime.utcnow()
    }
    res = newusers_col.insert_one(doc)
    return jsonify({"user_id": str(res.inserted_id)})

# ================================
# ADMIN
# ================================
@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        admin = admins_col.find_one({"username": request.form.get("username")})
        if admin and bcrypt.checkpw(
            request.form["password"].encode(),
            bytes(admin["password"])
        ):
            session["admin_logged_in"] = True
            return redirect("/admin")
        return "Invalid credentials", 401
    return render_template("admin_login.html")

@app.route("/admin")
@admin_required
def admin_dashboard():
    return "Admin Dashboard"

@app.route("/admin/logout")
def admin_logout():
    session.clear()
    return redirect("/")

# ================================
# CSV EXPORT
# ================================
@app.route("/api/admin/export_engagement_csv")
@admin_required
def export_csv():
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["user_id", "timestamp"])
    for e in eng_col.find():
        writer.writerow([e.get("user_id"), e.get("timestamp")])
    output.seek(0)
    return send_file(
        io.BytesIO(output.getvalue().encode()),
        mimetype="text/csv",
        download_name="engagements.csv",
        as_attachment=True
    )
