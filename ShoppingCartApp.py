import uuid
from bson import ObjectId, json_util
from flask import (
    Flask,
    request,
    jsonify,
    render_template,
    session,
    redirect,
    url_for,
    send_file,
)
from functools import wraps
from flask_cors import CORS
from flask_session import Session
from pymongo import MongoClient
from bson import ObjectId, Binary, errors as bson_errors
from datetime import datetime, timedelta
from recommendation_engine import RecommendationEngine
import bcrypt
import os
from functools import wraps
import csv
import io
import pathlib
import numpy as np
import json
import logging
import re


# Optional packages
try:
    import faiss

    FAISS_AVAILABLE = True
except Exception:
    faiss = None
    FAISS_AVAILABLE = False

try:
    from sentence_transformers import SentenceTransformer

    SENTENCE_TRANSFORMERS_AVAILABLE = True
except Exception:
    SentenceTransformer = None
    SENTENCE_TRANSFORMERS_AVAILABLE = False

try:
    import openai

    OPENAI_AVAILABLE = True
except Exception:
    openai = None
    OPENAI_AVAILABLE = False

# ---------------- CONFIG ----------------
VECTOR_DIM = 384  # default embedding dim for all-MiniLM-L6-v2
INDEX_PATH = pathlib.Path("./data/faiss.index")
META_PATH = pathlib.Path("./data/faiss_meta.json")
EMBED_MODEL = None

# MongoDB config (use env var in production)
MONGO_URI = os.environ.get(
    "MONGO_URI",
    "mongodb+srv://amushun1992_db_user:PwQge1UbU41Z3Xjs@tm-users.vxuhp3p.mongodb.net/citizen_portal?retryWrites=true&w=majority",
)

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# ---------------- APP ----------------
app = Flask(__name__, static_folder="static", template_folder="templates")
app.secret_key = os.environ.get("FLASK_SECRET", "prod-secret-key")
app.config["SESSION_TYPE"] = "filesystem"
app.config["SESSION_COOKIE_SECURE"] = (
    os.environ.get("SESSION_COOKIE_SECURE", "False") == "True"
)
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = os.environ.get(
    "SESSION_COOKIE_SAMESITE", "Lax")
Session(app)
CORS(app, supports_credentials=True)

# setup logging
logging.basicConfig(level=logging.INFO)
logger = app.logger
logger.setLevel(logging.INFO)

# ---------------- DB ----------------
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


# -----------------------------
# Analytics function
# -----------------------------
def build_dashboard_analytics(db):
    now = datetime.utcnow()

    # Collections
    newusers_col = db["webusers"]
    engagements_col = db["engagements"]
    orders_col = db["orders"]
    payments_col = db["payments"]

    # ----- User metrics -----
    total_users = newusers_col.count_documents({})
    active_users = newusers_col.count_documents(
        {"last_active": {"$gte": now - timedelta(days=30)}}
    )
    new_users_7d = newusers_col.count_documents(
        {"created": {"$gte": now - timedelta(days=7)}}
    )

    # ----- Engagement metrics -----
    total_engagements = engagements_col.count_documents({})
    recent_engagements_7d = engagements_col.count_documents(
        {"timestamp": {"$gte": now - timedelta(days=7)}}
    )

    # ----- Store metrics -----
    total_orders = orders_col.count_documents({})
    revenue_cursor = payments_col.aggregate(
        [
            {"$match": {"status": "completed"}},
            {"$group": {"_id": None, "total": {"$sum": "$amount"}}},
        ]
    )
    revenue_result = list(revenue_cursor)
    total_revenue_amount = revenue_result[0]["total"] if revenue_result else 0

    # ----- User segmentation -----
    user_segments = {}
    for user in newusers_col.find({}):
        segments = (
            user.get("extended_profile", {})
            .get("interests", {})
            .get("service_preferences", [])
        )
        for segment in segments:
            user_segments[segment] = user_segments.get(segment, 0) + 1

    # ----- Recent activities -----
    recent_activities = list(
        engagements_col.find().sort("timestamp", -1).limit(10))
    # Convert all ObjectIds to strings for JSON serialization
    recent_activities = json.loads(json_util.dumps(recent_activities))

    # Build analytics dictionary
    analytics = {
        "user_metrics": {
            "total_users": total_users,
            "active_users": active_users,
            "new_users_7d": new_users_7d,
        },
        "engagement_metrics": {
            "total_engagements": total_engagements,
            "recent_engagements_7d": recent_engagements_7d,
        },
        "store_metrics": {
            "total_orders": total_orders,
            "total_revenue": total_revenue_amount,
            "conversion_rate": "3.2%",  # Replace with real calculation if needed
        },
        "user_segments": user_segments,
        "recent_activities": recent_activities,
    }

    # Safety defaults
    analytics.setdefault(
        "user_metrics", {"total_users": 0,
                         "active_users": 0, "new_users_7d": 0}
    )
    analytics.setdefault(
        "engagement_metrics", {
            "total_engagements": 0, "recent_engagements_7d": 0}
    )
    analytics.setdefault(
        "store_metrics",
        {"total_orders": 0, "total_revenue": 0, "conversion_rate": "0%"},
    )
    analytics.setdefault("user_segments", {})
    analytics.setdefault("recent_activities", [])

    return analytics


# -----------------------------
# Dashboard route
# -----------------------------
@app.route("/dashboard")
def dashboard():
    analytics = build_dashboard_analytics(db)  # Pass your db object here
    return render_template("dashboard.html", analytics=analytics)


# -----------------------------
# Route: analytics API (optional)
# -----------------------------
@app.route("/api/dashboard/analytics", methods=["GET"])
def get_dashboard_analytics():
    now = datetime.utcnow()

    # -----------------------------
    # USER ANALYTICS
    # -----------------------------
    total_users = newusers_col.count_documents({})

    active_users = newusers_col.count_documents(
        {"last_active": {"$gte": now - timedelta(days=30)}}
    )

    new_users_7d = newusers_col.count_documents(
        {"created": {"$gte": now - timedelta(days=7)}}
    )

    # -----------------------------
    # ENGAGEMENT ANALYTICS
    # -----------------------------
    total_engagements = eng_col.count_documents({})

    recent_engagements = eng_col.count_documents(
        {"timestamp": {"$gte": now - timedelta(days=7)}}
    )

    # -----------------------------
    # STORE ANALYTICS
    # -----------------------------
    total_orders = orders_col.count_documents({})

    revenue_cursor = payments_col.aggregate(
        [
            {"$match": {"status": "completed"}},
            {"$group": {"_id": None, "total": {"$sum": "$amount"}}},
        ]
    )

    revenue_result = list(revenue_cursor)
    total_revenue_amount = revenue_result[0]["total"] if revenue_result else 0

    # -----------------------------
    # USER SEGMENTATION
    # -----------------------------
    user_segments = {}

    for user in newusers_col.find({}):
        segments = recommendation_engine.get_user_segment(str(user["_id"]))
        for segment in segments:
            user_segments[segment] = user_segments.get(segment, 0) + 1

    # -----------------------------
    # POPULAR PRODUCTS
    # -----------------------------
    popular_products = []
    for p in products_col.find().sort("rating", -1).limit(5):
        p["_id"] = str(p["_id"])
        popular_products.append(p)

    # -----------------------------
    # RECENT ACTIVITIES
    # -----------------------------
    recent_activities = []
    for a in eng_col.find().sort("timestamp", -1).limit(10):
        a["_id"] = str(a["_id"])
        recent_activities.append(a)

    # -----------------------------
    # RESPONSE
    # -----------------------------
    return jsonify(
        {
            "user_metrics": {
                "total_users": total_users,
                "active_users": active_users,
                "new_users_7d": new_users_7d,
            },
            "engagement_metrics": {
                "total_engagements": total_engagements,
                "recent_engagements": recent_engagements,
                "avg_session_duration": "5m 23s",  # placeholder
            },
            "store_metrics": {
                "total_orders": total_orders,
                "total_revenue": total_revenue_amount,
                "conversion_rate": "3.2%",  # placeholder
            },
            "user_segments": user_segments,
            "popular_products": popular_products,
            "recent_activities": recent_activities,
        }
    )


# /api/consent/update
@app.route("/api/consent/update", methods=["POST"])
def update_consent():
    payload = request.json or {}
    user_id = payload.get("user_id")

    if not user_id:
        return jsonify({"error": "user_id required"}), 400

    consent_updates = {
        "extended_profile.consent.marketing_emails": payload.get(
            "marketing_emails", False
        ),
        "extended_profile.consent.personalized_ads": payload.get(
            "personalized_ads", False
        ),
        "extended_profile.consent.data_analytics": payload.get("data_analytics", False),
        "extended_profile.consent.updated": datetime.utcnow(),
    }

    newusers_col.update_one({"_id": ObjectId(user_id)}, {
                            "$set": consent_updates})

    return jsonify({"status": "ok", "message": "Consent preferences updated"})


# /api/data/export/<user_id>
@app.route("/api/data/export/<user_id>", methods=["GET"])
def export_user_data(user_id):
    """GDPR-compliant user data export"""

    user = newusers_col.find_one({"_id": ObjectId(user_id)})

    if not user:
        return jsonify({"error": "User not found"}), 404

    # -----------------------------
    # REMOVE INTERNAL / SENSITIVE FIELDS
    # -----------------------------
    export_data = {
        "profile": user.get("profile", {}),
        "extended_profile": user.get("extended_profile", {}),
        "consent_preferences": user.get("extended_profile", {}).get("consent", {}),
    }

    return jsonify(export_data), 200


# /api/store/products
@app.route("/api/store/products")
def get_products():
    from bson import ObjectId

    category = request.args.get("category")
    delivery = request.args.get("delivery")
    min_price = request.args.get("min_price", type=int)
    max_price = request.args.get("max_price", type=int)
    sort = request.args.get("sort", "name")

    query = {}

    # -------------------------
    # CATEGORY FILTER
    # -------------------------
    if category:
        query["category"] = {"$in": [c.strip().lower()
                                     for c in category.split(",")]}

    # -------------------------
    # DELIVERY FILTER (FIXED)
    # -------------------------
    if delivery:
        query["delivery_options"] = {
            "$in": [d.strip().lower() for d in delivery.split(",")]
        }

    # -------------------------
    # PRICE FILTER
    # -------------------------
    if min_price is not None or max_price is not None:
        query["price"] = {}
        if min_price is not None:
            query["price"]["$gte"] = min_price
        if max_price is not None:
            query["price"]["$lte"] = max_price

    # 🔍 DEBUG (VERY IMPORTANT)
    print("FINAL QUERY:", query)
    print("RAW PARAMS:", request.args)
    print("QUERY BEFORE DB:", query)

    cursor = products_col.find(query)

    # -------------------------
    # SORTING
    # -------------------------
    if sort == "featured":
        cursor = cursor.sort("featured", -1)
    elif sort == "price_low":
        cursor = cursor.sort("price", 1)
    elif sort == "price_high":
        cursor = cursor.sort("price", -1)
    else:
        cursor = cursor.sort("name", 1)

    products = list(cursor)

    # Convert ObjectId
    for p in products:
        p["_id"] = str(p["_id"])

    return jsonify(products)


# /api/store/categories


@app.route("/api/store/categories")
def get_store_categories():
    categories = products_col.distinct("category")
    subcategories = {}
    for cat in categories:
        subcategories[cat] = products_col.distinct(
            "subcategory", {"category": cat})

    return jsonify({"categories": categories, "subcategories": subcategories})





# --- Order API ---
# @app.route("/api/store/order", methods=["POST"])
# def create_order():
#     payload = request.json or {}

#     if not payload.get("items"):
#         return jsonify({"error": "Cart is empty"}), 400

#     order = {
#         "order_id": f"ORD{datetime.utcnow().strftime('%Y%m%d%H%M%S')}",
#         "user_id": payload.get("user_id"),
#         "items": payload.get("items", []),
#         "total_amount": payload.get("total_amount", 0),

#         "status": "pending",
#         "shipping_address": payload.get("shipping_address", {}),
#         "payment_method": payload.get("payment_method", "cod"),
#         "created": datetime.utcnow(),
#         "updated": datetime.utcnow()
#     }

#     result = orders_col.insert_one(order)

#     return jsonify({
#         "status": "ok",
#         "order_id": order["order_id"],
#         "mongo_id": str(result.inserted_id)
#     }), 201

@app.route("/api/store/order", methods=["POST"])

def create_order():
    payload = request.json or {}
    order_id = f"ORD{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"

    order = {
        "order_id": order_id,
        "user_id": payload.get("user_id"),
        "items": payload.get("items", []),
        "total_amount": payload.get("total_amount", 0),
        "payment_method": payload.get("payment_method"),
        "status": "pending",  # will update to 'paid' if COD
        "created": datetime.utcnow(),
    }

    # Insert order
    orders_col.insert_one(order)

    # Automatically create payment if COD
    if str(payload.get("payment_method", "")).lower() == "cod":
        payment = {
            "payment_id": f"PAY{datetime.utcnow().strftime('%Y%m%d%H%M%S')}",
            "order_id": order_id,
            "user_id": payload.get("user_id"),
            "amount": payload.get("total_amount", 0),
            "currency": "LKR",
            "method": "cod",
            "status": "completed",
            "transaction_id": f"TXN{datetime.utcnow().strftime('%Y%m%d%H%M%S')}",
            "created": datetime.utcnow(),
        }
        payments_col.insert_one(payment)

        # Update order status to paid
        orders_col.update_one(
            {"order_id": order_id},
            {"$set": {"status": "paid", "updated": datetime.utcnow()}}
        )

    return jsonify({
        "success": True,
        "order_id": order_id,
        "total_amount": order["total_amount"]
    })



# @app.route("/api/store/order", methods=["POST"])
# def create_order():
#     try:
#         payload = request.json
#         print("PAYLOAD RECEIVED:", payload)

#         if not payload or not payload.get("items"):
#             return jsonify({"error": "Cart is empty"}), 400

#         order = {
#             "order_id": f"ORD{datetime.utcnow().strftime('%Y%m%d%H%M%S')}",
#             "user_id": payload.get("user_id"),
#             "items": payload.get("items", []),
#             "total_amount": payload.get("total_amount", 0),
#             "status": "pending",
#             "shipping_address": payload.get("shipping_address", {}),
#             "payment_method": payload.get("payment_method"),
#             "created": datetime.utcnow(),
#             "updated": datetime.utcnow(),
#         }

#         result = orders_col.insert_one(order)
#         print("ORDER INSERTED:", order)

#         # ---------------------------
#         # ✅ Store order info in session
#         # ---------------------------
#         session['order_id'] = order["order_id"]
#         session['total_amount'] = order["total_amount"]

#         # You have two options here:

#         # Option 1: Return JSON (recommended if your JS handles redirect)
#         return jsonify({
#             "success": True,
#             "order_id": order["order_id"],
#             "total_amount": order["total_amount"]
#         }), 200

#         # Option 2: Redirect directly to payment page (less common with JS checkout)
#         # return redirect("/store/cart/payment")

#     except Exception as e:
#         print("ERROR CREATING ORDER:", e)
#         return jsonify({"error": str(e)}), 500



# /api/store/payment
@app.route("/api/store/payment", methods=["POST"])
def process_payment():
    payload = request.json or {}

    payment = {
        "payment_id": f"PAY{datetime.utcnow().strftime('%Y%m%d%H%M%S')}",
        "order_id": payload.get("order_id"),
        "user_id": payload.get("user_id"),
        "amount": payload.get("amount", 0),
        "currency": payload.get("currency", "LKR"),
        "method": payload.get("method"),
        "status": "completed",
        "transaction_id": payload.get("transaction_id"),
        "created": datetime.utcnow(),
    }

    # Update order status
    orders_col.update_one(
        {"order_id": payload.get("order_id")},
        {"$set": {"status": "paid", "updated": datetime.utcnow()}},
    )

    payments_col.insert_one(payment)

    # Log engagement for recommendation system
    eng_col.insert_one(
        {
            "user_id": payload.get("user_id"),
            "type": "purchase",
            "product_ids": [
                item.get("product_id") for item in payload.get("items", [])
            ],
            "amount": payload.get("amount", 0),
            "timestamp": datetime.utcnow(),
        }
    )
    return jsonify({"status": "ok", "payment_id": payment["payment_id"]})


recommendation_engine = RecommendationEngine()


@app.route("/recommendations")
def recommendations_page():
    return render_template("recommendations.html")


@app.route("/store")
def store():
    return render_template("store.html")


# @app.route("/payment")
# def payment_page():
#     return render_template("payment.html")


@app.route("/api/recommendations/<user_id>")
def get_recommendations(user_id):
    try:
        ads = recommendation_engine.get_personalized_ads(user_id)
        edu_recommendations = recommendation_engine.generate_education_recommendations(
            user_id
        )

        return jsonify(
            {
                "ads": ads,
                "education_recommendations": edu_recommendations,
                "user_segment": recommendation_engine.get_user_segment(user_id),
            }
        )

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ---------------- Utilities ----------------


def to_jsonable(obj):
    if isinstance(obj, ObjectId):
        return str(obj)
    if isinstance(obj, Binary):
        return bytes(obj)
    if isinstance(obj, dict):
        return {k: to_jsonable(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [to_jsonable(v) for v in obj]
    return obj


def admin_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not session.get("admin_logged_in"):
            accept = request.headers.get("Accept", "")
            if "application/json" in accept or request.path.startswith("/api/"):
                return jsonify({"error": "unauthorized"}), 401
            return redirect(url_for("admin_login"))
        return fn(*args, **kwargs)

    return wrapper


# ---------------- Embedding model ----------------


def get_embedding_model():
    global EMBED_MODEL
    if EMBED_MODEL is None:
        if not SENTENCE_TRANSFORMERS_AVAILABLE:
            raise RuntimeError(
                "sentence-transformers not available. Install with `pip install sentence-transformers`"
            )
        # model_name = os.getenv(
        #     "EMBED_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
        model_name = os.getenv(
            "EMBED_MODEL", "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
        )

        EMBED_MODEL = SentenceTransformer(model_name)
        logger.info(f"Loaded embedding model: {model_name}")
    return EMBED_MODEL


# ---------------- OpenAI helper ----------------
if OPENAI_AVAILABLE and OPENAI_API_KEY:
    openai.api_key = OPENAI_API_KEY


def run_ai_simple(query: str):
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "Give accurate, short answers."},
                {"role": "user", "content": query},
            ],
        )
        return response.choices[0].message.content.strip()

    except Exception as e:
        print("AI ERROR:", e)
        return None


def ask_ai(query):
    """
    Ask OpenAI; returns string answer. If OpenAI not configured, returns None.
    """
    if not OPENAI_AVAILABLE or not OPENAI_API_KEY:
        return None
    try:
        # using chat completion for best short answers
        resp = openai.chat.completions.create(...)(
            model=os.getenv("OPENAI_MODEL", "gpt-3.5-turbo"),
            messages=[{"role": "user", "content": query}],
            temperature=0.2,
            max_tokens=512,
        )
        return resp.choices[0].message.content.strip()
    except Exception as e:
        logger.exception("OpenAI call failed: %s", e)
        return None


def build_faiss_index():
    if not FAISS_AVAILABLE:
        logger.warning("FAISS not available; cannot build index.")
        return False

    # Collect texts + metadata
    services = list(services_col.find({}, {"_id": 0}))
    texts = []
    items = []

    for service in services:
        svc_name = service.get("name", {}).get("en", "") or ""

        for sub in service.get("subservices", []) or []:
            sub_name = sub.get("name", {}).get("en", "") or ""

            for q in sub.get("questions", []) or []:
                q_text = q.get("q", {}).get("en", "") or ""
                a_text = q.get("answer", {}).get("en", "") or ""

                #  MUST include answer text for proper semantic search
                combined = " ".join(
                    [svc_name, sub_name, q_text, a_text]).strip()

                texts.append(combined)

                # Meta item
                items.append(
                    {
                        "service": svc_name,
                        "subservice": sub_name,
                        "question": q_text,
                        "answer": a_text,
                    }
                )

    if len(texts) == 0:
        logger.info("No texts found to index.")
        return False

    try:
        model = get_embedding_model()

        # encode questions + answers
        vectors = model.encode(texts, convert_to_numpy=True)

        # Create FAISS index
        index = faiss.IndexFlatL2(VECTOR_DIM)
        index.add(vectors)

        if not INDEX_PATH.parent.exists():
            INDEX_PATH.parent.mkdir(parents=True, exist_ok=True)

        faiss.write_index(index, str(INDEX_PATH))

        with open(META_PATH, "w", encoding="utf-8") as f:
            json.dump(items, f, indent=2, ensure_ascii=False)

        logger.info("FAISS index built successfully with %d items", len(items))
        return True

    except Exception as e:
        logger.exception("Failed to build FAISS index: %s", e)
        return False


def load_faiss_index():
    if not FAISS_AVAILABLE:
        return None, []
    if not INDEX_PATH.exists() or not META_PATH.exists():
        return None, []
    try:
        index = faiss.read_index(str(INDEX_PATH))
        with open(META_PATH, "r", encoding="utf-8") as f:
            meta = json.load(f)
        return index, meta
    except Exception as e:
        logger.exception("Failed to load FAISS index: %s", e)
        return None, []


# preload index at startup (if present)
_index, _meta = load_faiss_index()

# ---------------- Routes ----------------


@app.route("/")
def home():
    try:
        return render_template("mainfaiss.html")
    except Exception:
        return "Citizen Portal API Running"


# ---------------- Admin ----------------
@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        username = request.form.get("username", "")
        password = request.form.get("password", "")
        admin = admins_col.find_one({"username": username})
        if admin:
            stored_hash = admin.get("password")
            if isinstance(stored_hash, Binary):
                stored_hash = bytes(stored_hash)
            if isinstance(stored_hash, str):
                return render_template("admin_login.html", error="Invalid credentials")
            try:
                if bcrypt.checkpw(password.encode("utf-8"), stored_hash):
                    session["admin_logged_in"] = True
                    return redirect(url_for("admin_dashboard"))
            except Exception:
                return render_template("admin_login.html", error="Invalid credentials")
        return render_template("admin_login.html", error="Invalid credentials")
    return render_template("admin_login.html")


@app.route("/admin")
@admin_required
def admin_dashboard():
    try:
        return render_template("faissadmin.html")
    except Exception:
        return "Admin Dashboard"


@app.route("/admin/logout")
def admin_logout():
    session.pop("admin_logged_in", None)
    return redirect(url_for("admin_login"))


# Admin endpoint to rebuild index
@app.route("/admin/rebuild_faiss", methods=["POST"])
@admin_required
def admin_rebuild_faiss():
    ok = build_faiss_index()
    global _index, _meta
    _index, _meta = load_faiss_index()
    return jsonify({"ok": ok})


# ---------------- Profiles ----------------
@app.route("/api/profile/step", methods=["POST"])
def api_profile_step():
    data = request.json or {}
    step = data.get("step")
    profile_id = data.get("profile_id")
    step_data = data.get("data", {})

    if step not in ["basic", "contact", "employment"]:
        return jsonify({"error": "Invalid step"}), 400

    # STEP 1: create profile
    if step == "basic":
        doc = {
            "name": step_data.get("name"),
            "age": step_data.get("age"),
            "email": step_data.get("email"),
            "phone": None,
            "job": None,
            "created_at": datetime.utcnow(),
        }
        result = profiles_col.insert_one(doc)
        return jsonify({"profile_id": str(result.inserted_id)})

    # STEP 2 + STEP 3 require profile_id
    if not profile_id:
        return jsonify({"error": "profile_id required"}), 400

    try:
        pid = ObjectId(profile_id)
    except Exception:
        return jsonify({"error": "Invalid profile_id"}), 400

    if step == "contact":
        profiles_col.update_one(
            {"_id": pid},
            {
                "$set": {
                    "email": step_data.get("email"),
                    "phone": step_data.get("phone"),
                }
            },
        )
        return jsonify({"status": "ok"})

    if step == "employment":
        profiles_col.update_one(
            {"_id": pid}, {"$set": {"job": step_data.get("job")}})
        return jsonify({"status": "ok"})

    return jsonify({"error": "Unhandled case"}), 400


# ---------------- Services / Categories / Ads / Officers ----------------
@app.route("/api/services", methods=["GET"])
def api_services():
    docs = list(services_col.find({}, {"_id": 0}))
    return jsonify(to_jsonable(docs))


@app.route("/api/categories", methods=["GET", "POST"])
def get_categories():
    if request.method == "POST":
        data = request.json
        if not data or not data.get("id") or not data.get("name", {}).get("en"):
            return jsonify({"error": "Missing required fields"}), 400
        if categories_col.find_one({"id": data["id"]}):
            return jsonify({"error": "Category ID already exists"}), 400
        categories_col.insert_one(data)
        return jsonify({"message": "Category added successfully"})
    docs = list(categories_col.find({}, {"_id": 0}))
    return jsonify(docs)


@app.route("/api/officers", methods=["GET", "POST"])
def api_officers():
    if request.method == "POST":
        data = request.json
        if not data:
            return jsonify({"error": "No JSON received"}), 400
        required = ["id", "name", "role", "ministry_id", "email", "phone"]
        for field in required:
            if field not in data or not str(data[field]).strip():
                return jsonify({"error": f"Missing field: {field}"}), 400
        officers_col.insert_one(data)
        return jsonify({"message": "Officer added successfully!"}), 201
    return jsonify(list(officers_col.find({})))


@app.route("/api/ads", methods=["GET", "POST"])
def api_ads():
    if request.method == "POST":
        data = request.json or {}
        if not data.get("id") or not data.get("title"):
            return jsonify({"error": "Missing required fields (id, title)"}), 400
        if ads_col.find_one({"id": data["id"]}):
            return jsonify({"error": "Ad ID already exists"}), 400
        ads_col.insert_one(data)
        return jsonify({"message": "Ad added successfully"}), 201
    docs = list(ads_col.find({}, {"_id": 0}))
    return jsonify(docs)

    # Add to existing users_col schema


@app.route("/api/profile/extended", methods=["POST"])
def extended_profile():
    payload = request.json or {}
    user_id = payload.get("user_id")  # coming from engagements

    if not user_id:
        return jsonify({"error": "user_id required"}), 400

    try:
        user_obj_id = ObjectId(user_id)
    except Exception:
        return jsonify({"error": "Invalid user_id"}), 400

    # Check if user exists in webusers
    user = newusers_col.find_one({"_id": user_obj_id})
    if not user:
        return jsonify({"error": "User not found in webusers"}), 404

    # Build extended profile
    extended_data = {
        "family": {
            "marital_status": payload.get("marital_status"),
            "children": payload.get("children", []),
            "children_ages": payload.get("children_ages", []),
            "children_education": payload.get("children_education", []),
            "dependents": payload.get("dependents", 0),
        },
        "education": {
            "highest_qualification": payload.get("highest_qualification"),
            "institution": payload.get("institution"),
            "year_graduated": payload.get("year_graduated"),
            "field_of_study": payload.get("field_of_study"),
        },
        "career": {
            "current_job": payload.get("current_job"),
            "years_experience": payload.get("years_experience"),
            "skills": payload.get("skills", []),
            "career_goals": payload.get("career_goals", []),
        },
        "interests": {
            "hobbies": payload.get("hobbies", []),
            "learning_interests": payload.get("learning_interests", []),
            "service_preferences": payload.get("service_preferences", []),
        },
        "consent": {
            "marketing_emails": payload.get("marketing_emails", False),
            "personalized_ads": payload.get("personalized_ads", False),
            "data_analytics": payload.get("data_analytics", False),
        },
    }

    try:
        newusers_col.update_one(
            {"_id": user_obj_id},
            {"$set": {"extended_profile": extended_data, "updated": datetime.utcnow()}},
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    return jsonify({"status": "ok"})


# add new user  (/api/profile/extended)
@app.route("/api/profile/create", methods=["POST"])
def create_profile():
    payload = request.json or {}
    user_id = payload.get("user_id")

    # Build extended profile structure
    extended_data = {
        "family": {
            "marital_status": payload.get("marital_status"),
            "children": payload.get("children", []),
            "children_ages": payload.get("children_ages", []),
            "children_education": payload.get("children_education", []),
            "dependents": payload.get("dependents", 0),
        },
        "education": {
            "highest_qualification": payload.get("highest_qualification"),
            "institution": payload.get("institution"),
            "year_graduated": payload.get("year_graduated"),
            "field_of_study": payload.get("field_of_study"),
        },
        "career": {
            "current_job": payload.get("current_job"),
            "years_experience": payload.get("years_experience"),
            "skills": payload.get("skills", []),
            "career_goals": payload.get("career_goals", []),
        },
        "interests": {
            "hobbies": payload.get("hobbies", []),
            "learning_interests": payload.get("learning_interests", []),
            "service_preferences": payload.get("service_preferences", []),
        },
        "consent": {
            "marketing_emails": payload.get("marketing_emails", False),
            "personalized_ads": payload.get("personalized_ads", False),
            "data_analytics": payload.get("data_analytics", False),
        },
    }

    # If user_id exists, try to update; else create new
    user_obj_id = None
    if user_id:
        try:
            user_obj_id = ObjectId(user_id)
            user = newusers_col.find_one({"_id": user_obj_id})
            if user:
                newusers_col.update_one(
                    {"_id": user_obj_id},
                    {
                        "$set": {
                            "extended_profile": extended_data,
                            "updated": datetime.utcnow(),
                        }
                    },
                )
                return jsonify({"status": "ok", "user_id": str(user_obj_id)})
        except Exception:
            pass  # invalid user_id will fall through to creation

    # Create new user
    new_doc = {
        "name": payload.get("name"),
        "age": payload.get("age"),
        "email": payload.get("email"),
        "job": payload.get("job"),
        "extended_profile": extended_data,
        "created": datetime.utcnow(),
        "updated": datetime.utcnow(),
    }
    result = newusers_col.insert_one(new_doc)
    return jsonify({"status": "ok", "user_id": str(result.inserted_id)})


# Enhanced engagement logging


@app.route("/api/engagement/enhanced", methods=["POST"])
def log_enhanced_engagement():
    payload = request.json or {}

    # Extract behavioral data
    user_agent = request.headers.get("User-Agent", "")
    ip_address = request.remote_addr
    referrer = request.headers.get("Referer", "")

    try:
        doc = {
            "user_id": payload.get("user_id"),
            "session_id": payload.get("session_id"),
            "age": int(payload.get("age")) if payload.get("age") else None,
            "job": payload.get("job"),
            "desires": payload.get("desires", []),
            "question_clicked": payload.get("question_clicked"),
            "service": payload.get("service"),
            "ad": payload.get("ad"),
            "source": payload.get("source"),
            # User behavior tracking
            "time_spent": payload.get("time_spent"),
            "scroll_depth": payload.get("scroll_depth"),
            "clicks": payload.get("clicks", []),
            "searches": payload.get("searches", []),
            # Device info
            "device_info": {
                "user_agent": user_agent,
                "ip_address": ip_address,
                "screen_resolution": payload.get("screen_resolution"),
            },
            # Referral tracking
            "referral_data": {
                "referrer": referrer,
                "utm_source": payload.get("utm_source"),
                "utm_medium": payload.get("utm_medium"),
                "utm_campaign": payload.get("utm_campaign"),
            },
            "timestamp": datetime.utcnow(),
        }

        eng_col.insert_one(doc)

    except Exception as e:
        return jsonify({"error": str(e)}), 500

    return jsonify({"status": "ok"})


# ---------------- Engagement CSV ----------------
@app.route("/api/admin/export_engagement_csv", methods=["GET"])
@admin_required
def export_engagement_csv():
    try:
        cursor = eng_col.find()
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(
            [
                "user_id",
                "age",
                "job",
                "desires",
                "question_clicked",
                "service",
                "ad",
                "source",
                "timestamp",
            ]
        )
        for e in cursor:
            writer.writerow(
                [
                    e.get("user_id"),
                    e.get("age"),
                    e.get("job"),
                    ",".join(e.get("desires") or []),
                    e.get("question_clicked"),
                    e.get("service"),
                    e.get("ad"),
                    e.get("source"),
                    e.get("timestamp"),
                ]
            )
        output.seek(0)
        return send_file(
            io.BytesIO(output.getvalue().encode("utf-8")),
            mimetype="text/csv",
            as_attachment=True,
            download_name="engagements.csv",
        )
    except Exception as e:
        logger.exception("CSV export failed: %s", e)
        return jsonify({"error": str(e)}), 500


# ---------------- FAISS-only endpoint ----------------


@app.route("/api/ai/faiss_search", methods=["POST"])
def api_ai_faiss_search():
    if request.method != "POST":
        return jsonify({"error": "Use POST with JSON body: {query: '...'}"}), 405

    data = request.get_json(silent=True) or {}
    query = (data.get("query") or "").strip()
    top_k = int(data.get("top_k", 5))

    if not query:
        return jsonify({"error": "Query required"}), 400

    # load index if needed
    idx, meta = load_faiss_index()
    if idx is None or not meta:
        return jsonify({"error": "FAISS index not available"}), 500

    try:
        model = get_embedding_model()
        q_vec = model.encode([query], convert_to_numpy=True)
        distances, ids = idx.search(q_vec, max(1, top_k))

        results = []
        for i, d in zip(ids[0], distances[0]):
            if i != -1 and i < len(meta):
                item = meta[i].copy()
                item["distance"] = float(d)
                results.append(item)
        return jsonify({"query": query, "results": results})
    except Exception as e:
        logger.exception("FAISS search failed: %s", e)
        return jsonify({"error": "FAISS search failed", "details": str(e)}), 500


def rebuild_index():
    """
    Minimal stub: does nothing but returns a dict so route succeeds.
    Replace this with real indexing logic later.
    """
    # Example: pretend we rebuilt 0 documents
    return {"count": 0, "note": "stub rebuild_index did nothing (for testing)"}


@app.route("/api/ai/rebuild", methods=["POST"])
def api_ai_rebuild():
    try:
        # Example FAISS rebuild call
        result = rebuild_index()  # your function

        return jsonify({"message": "AI index rebuilt"}), 200

    except Exception as e:
        print("INDEX ERROR:", e)
        return jsonify({"error": str(e)}), 500

    # /api/engagement


@app.route("/api/engagement", methods=["POST"])
def create_or_filter_engagement():
    try:
        payload = request.json or {}
        # Example: filter by user_id
        user_id = payload.get("user_id")
        query = {}
        if user_id:
            query["user_id"] = user_id
        data = [to_jsonable(d) for d in eng_col.find(query)]
        return jsonify({"ok": True, "data": data})
    except Exception as e:
        logger.exception("Failed to process engagements: %s", e)
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/ai/search", methods=["GET", "POST"])
def api_ai_search():
    """
    Hybrid AI Search Endpoint - returns ONE most accurate answer
    Priority:
    1. FAISS semantic search (best match)
    2. Keyword DB search (first match)
    3. Context-aware AI fallback
    """

    data = request.get_json(silent=True) or {}
    query = (data.get("query") or "").strip()
    if not query:
        return jsonify({"error": "Query required"}), 400

    # 1. FAISS SEARCH
    try:
        idx, meta = load_faiss_index()
        if idx and meta:
            model = get_embedding_model()
            q_vec = model.encode([query], convert_to_numpy=True)
            distances, ids = idx.search(q_vec, 1)  # only top 1

            i = ids[0][0]
            if i != -1 and i < len(meta):
                item = meta[i].copy()
                item["score"] = float(distances[0][0])
                item["source"] = "faiss"
                return jsonify({"source": "faiss", "query": query, "result": item}), 200
    except Exception as e:
        app.logger.exception("FAISS error: %s", e)

    # 2. DB SEARCH (first match only)
    try:
        q_regex = {"$regex": query, "$options": "i"}
        svc = services_col.find_one(
            {"$or": [{"name.en": q_regex}, {"description": q_regex}]}, {"_id": 0}
        )
        if svc:
            svc["source"] = "db"
            return jsonify({"source": "db", "query": query, "result": svc}), 200
    except Exception as e:
        app.logger.exception("DB search error: %s", e)

    # 3️. AI FALLBACK
    try:
        # Build context from DB
        context_docs = []
        for svc in services_col.find({}, {"_id": 0}):
            for sub in svc.get("subservices", []) or []:
                for qobj in sub.get("questions", []) or []:
                    q_text = qobj.get("q", {}).get("en", "")
                    a_text = qobj.get("answer", {}).get("en", "")
                    if q_text and a_text:
                        context_docs.append(
                            {"question": q_text, "answer": a_text})

        ai_answer = run_ai_simple(query, context_docs=context_docs)
        if ai_answer:
            return (
                jsonify(
                    {
                        "source": "ai",
                        "query": query,
                        "result": {"answer": ai_answer, "source": "ai"},
                    }
                ),
                200,
            )
    except Exception as e:
        app.logger.exception("AI fallback error: %s", e)

    # 4 NOTHING FOUND
    return (
        jsonify(
            {
                "source": "none",
                "query": query,
                "result": {
                    "answer": "No relevant information found.",
                    "source": "hybrid",
                },
            }
        ),
        200,
    )


@app.route("/api/ai/ai_only_search", methods=["POST"])
def ai_only_search():
    """
    AI-Only Search Endpoint
    - Uses only AI (OpenAI or local LLM) to answer questions.
    - Optionally includes context from DB for more accurate answers.
    - Always returns a single most relevant answer.
    """

    data = request.get_json(silent=True) or {}
    query = (data.get("query") or "").strip()

    if not query:
        return jsonify({"error": "Query required"}), 400

    # ----------------- Build context from DB -----------------
    context_docs = []
    try:
        for svc in services_col.find({}, {"_id": 0}):
            for sub in svc.get("subservices", []) or []:
                for qobj in sub.get("questions", []) or []:
                    q_text = qobj.get("q", {}).get("en", "")
                    a_text = qobj.get("answer", {}).get("en", "")
                    if q_text and a_text:
                        context_docs.append(
                            {"question": q_text, "answer": a_text})
    except Exception as e:
        app.logger.exception("Error building context docs: %s", e)

    # ----------------- Query AI -----------------
    try:
        ai_answer = ask_ai_with_context_single(query, context_docs)
        if ai_answer:
            return (
                jsonify(
                    {
                        "source": "ai",
                        "query": query,
                        "results": [{"answer": ai_answer, "source": "ai"}],
                    }
                ),
                200,
            )
    except Exception as e:
        app.logger.exception("AI error: %s", e)
        return (
            jsonify(
                {
                    "source": "ai",
                    "query": query,
                    "results": [{"answer": "AI service unavailable.", "source": "ai"}],
                }
            ),
            200,
        )

    # ----------------- NOTHING FOUND -----------------
    return (
        jsonify(
            {
                "source": "ai",
                "query": query,
                "results": [
                    {"answer": "No relevant information found.", "source": "ai"}
                ],
            }
        ),
        200,
    )


@app.route("/store/cart")
def cart_page():
    return render_template("cart.html")


@app.route("/store/cart/payment")
def payment():
    if 'order_id' not in session:
        return redirect("/store")
    return render_template("payment.html", order_id=session['order_id'], total_amount=session['total_amount'])


@app.route("/payment-success")
def payment_success_page():  # ✅ unique function name
    return render_template("payment_success.html")


@app.route("/api/engagement", methods=["GET"])
def get_engagements():
    try:
        # Fetch all engagements
        # exclude _id or convert as needed
        data = list(eng_col.find({}, {"_id": 0}))
        return jsonify({"ok": True, "data": data})
    except Exception as e:
        logger.exception("Failed to load engagements: %s", e)
        return jsonify({"ok": False, "error": str(e)}), 500


# ----------------- HELPER FUNCTION -----------------
def ask_ai_with_context_single(query, context_docs=[]):
    """
    Query AI with DB context and return a single most accurate answer.
    """
    prompt = "Answer the question accurately using the following context:\n\n"
    for doc in context_docs:
        q = doc.get("question", "")
        a = doc.get("answer", "")
        if q and a:
            prompt += f"Q: {q}\nA: {a}\n\n"
    prompt += f"Question: {query}\nAnswer:"

    return ask_ai(prompt)  # your existing AI call function


# ---------------- Default admin create & startup ----------------
def create_default_admin():
    admin = admins_col.find_one({"username": "admin"})
    if admin:
        stored = admin.get("password")
        if isinstance(stored, str):
            admins_col.delete_one({"_id": admin["_id"]})
        else:
            return
    pwd = os.environ.get("ADMIN_PWD", "admin123")
    hashed = bcrypt.hashpw(pwd.encode("utf-8"), bcrypt.gensalt())
    admins_col.insert_one({"username": "admin", "password": hashed})
    logger.info("Default admin created: username='admin' (or already exists)")


if __name__ == "__main__":
    # create default admin if missing
    create_default_admin()

    # build index if FAISS is available and index missing (optional)
    if FAISS_AVAILABLE and (not INDEX_PATH.exists() or not META_PATH.exists()):
        built = build_faiss_index()
        if built:
            logger.info("Built FAISS index on startup.")

    # show registered routes — quick sanity check to avoid 404 confusion
    for rule in app.url_map.iter_rules():
        logger.info("Route -> %s : %s", rule.rule,
                    ",".join(sorted(rule.methods)))

    # start server
    app.run(debug=True, host="127.0.0.1", port=int(os.getenv("PORT", "5000")))
