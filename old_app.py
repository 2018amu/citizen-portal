import os
import json
import numpy as np
import pandas as pd
import bcrypt
from datetime import datetime
from io import StringIO, BytesIO
import csv
from flask import Flask, jsonify, render_template, request, session, redirect, send_file,url_for
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from pymongo import MongoClient
from bson import ObjectId
from dotenv import load_dotenv
from sentence_transformers import SentenceTransformer
from chromadb.utils import embedding_functions
import chromadb
from sklearn.cluster import KMeans
from openai import OpenAI
from werkzeug.security import generate_password_hash, check_password_hash

# --- Set HF cache ---
os.environ["HF_HOME"] = "D:/huggingface_cache"

# --- Flask app ---
app = Flask(__name__, static_folder="static", template_folder="templates")

# --- Load .env ---
load_dotenv(dotenv_path="C:/Users/User/Desktop/Citizan-portal/.env")

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
MONGO_URI = os.getenv("MONGO_URI")
FLASK_SECRET = os.getenv("FLASK_SECRET", "dev-secret")

if not OPENAI_API_KEY or not MONGO_URI:
    raise ValueError("OPENAI_API_KEY or MONGO_URI missing in .env")

app.secret_key = FLASK_SECRET
CORS(app)

# --- Rate limiter ---
limiter = Limiter(key_func=get_remote_address, default_limits=["200/day", "50/hour"])
limiter.init_app(app)

# --- MongoDB ---
mongo_client = MongoClient(MONGO_URI)
db = mongo_client["citizen_portal"]
services_col = db["services"]
eng_col = db["engagements"]
admins_col = db["admins"]


if admins_col.count_documents({}) == 0:
    default_pwd = os.getenv("ADMIN_PWD", "admin123")
    hashed_pwd = generate_password_hash(default_pwd)
    admins_col.insert_one({"username": "admin", "password": hashed_pwd})

# --- OpenAI ---
openai_client = OpenAI(api_key=OPENAI_API_KEY)

# --- Embeddings & Chroma ---
embedder = SentenceTransformer("all-MiniLM-L6-v2")
embedding_function = embedding_functions.SentenceTransformerEmbeddingFunction(
    model_name="all-MiniLM-L6-v2"
)

chroma_client = chromadb.PersistentClient(path="./vectorstore")
collection = chroma_client.get_or_create_collection(
    name="citizen_services", embedding_function=embedding_function
)

def admin_required(fn):
    from functools import wraps
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not session.get("admin_logged_in"):
            # If it's an API call → return JSON
            if request.path.startswith("/api/"):
                return jsonify({"error": "unauthorized"}), 401
            # If it's a normal page → redirect
            return redirect(url_for("admin_login"))
        return fn(*args, **kwargs)
    return wrapper



# --- Public routes ---
@app.route("/")
def home():
    return render_template("index.html")


@app.route("/api/services")
def get_services():
    docs = list(services_col.find({}, {"_id": 0}))
    return jsonify(docs)


@app.route("/api/service/<service_id>")
def get_service(service_id):
    doc = services_col.find_one({"id": service_id}, {"_id": 0})
    return jsonify(doc or {})


@app.route("/api/engagement", methods=["POST"])
@limiter.limit("20/minute")
def log_engagement():
    payload = request.json or {}
    doc = {
        "user_id": payload.get("user_id") or None,
        "age": int(payload.get("age")) if payload.get("age") else None,
        "job": payload.get("job") or [],
        "desires": payload.get("desires"),
        "question_clicked": payload.get("question_clicked"),
        "service": payload.get("service"),
        "timestamp": datetime.utcnow(),
    }
    eng_col.insert_one(doc)
    return jsonify({"status": "ok"})


# --- Admin routes ---
@app.route("/admin/login", methods=["GET"])
def admin_login_page():
    return render_template("admin.html")

@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":

        data = request.get_json(silent=True) or request.form or {}

        username = data.get("username", "").strip()
        password = data.get("password", "").strip()

        admin = admins_col.find_one({"username": username})
        if not admin:
            return jsonify({"error": "Invalid username or password"}), 401

        stored_hash = admin.get("password")

        # Convert stored hash into bytes if needed
        if isinstance(stored_hash, str):
            stored_hash = stored_hash.encode("utf-8")

        # Convert input password into bytes
        password_bytes = password.encode("utf-8")

        # Validate password
        if bcrypt.checkpw(password_bytes, stored_hash):
            session["admin_logged_in"] = True
            return jsonify({"message": "ok"}), 200

        return jsonify({"error": "Invalid username or password"}), 401

    # If GET → show login page
    return render_template("admin_login.html")

def create_default_admin():
    admin = admins_col.find_one({"username": "admin"})
    if not admin:
        pwd = os.getenv("ADMIN_PWD", "admin123")
        hashed = bcrypt.hashpw(pwd.encode("utf-8"), bcrypt.gensalt())
        admins_col.insert_one({
            "username": "admin",
            "password": hashed
        })
        print("✔ Default admin created (admin / admin123)")




@app.route("/api/admin/logout", methods=["POST"])
def admin_logout():
    session.clear()
    return jsonify({"status": "logged out", "message": "Admin session cleared."})


# --- Admin Insights & ML clustering ---
@app.route("/api/admin/insights")
@admin_required
def admin_insights():
    # Age groups
    age_groups = {"<18": 0, "18-25": 0, "26-40": 0, "41-60": 0, "60+": 0}
    for e in eng_col.find({}, {"age": 1}):
        age = e.get("age")
        if age:
            age = int(age)
            if age < 18:
                age_groups["<18"] += 1
            elif age <= 25:
                age_groups["18-25"] += 1
            elif age <= 40:
                age_groups["26-40"] += 1
            elif age <= 60:
                age_groups["41-60"] += 1
            else:
                age_groups["60+"] += 1

    # Jobs
    jobs = {}
    for e in eng_col.find({}, {"job": 1}):
        j = e.get("job") or "Unknown"
        if isinstance(j, list):
            j = ",".join(j) or "Unknown"
        jobs[j] = jobs.get(j, 0) + 1

    # Services, questions, desires
    services, questions, desires = {}, {}, {}
    for e in eng_col.find({}, {"service": 1, "question_clicked": 1, "desires": 1}):
        s = e.get("service") or "Unknown"
        q = e.get("question_clicked") or "Unknown"
        ds = e.get("desires") or []
        services[s] = services.get(s, 0) + 1
        questions[q] = questions.get(q, 0) + 1
        for d in ds:
            desires[d] = desires.get(d, 0) + 1

    # Simple repeated engagements
    pipeline = [
        {
            "$group": {
                "_id": {"user": "$user_id", "question": "$question_clicked"},
                "count": {"$sum": 1},
            }
        },
        {"$match": {"count": {"$gte": 2}}},
    ]
    repeated = list(eng_col.aggregate(pipeline))
    premium_suggestions = [
        {
            "user": r["_id"]["user"],
            "question": r["_id"]["question"],
            "count": r["count"],
        }
        for r in repeated
        if r["_id"]["user"]
    ]

    # ML-based clustering for premium help
    data = list(eng_col.find({}, {"user_id": 1, "question_clicked": 1}))
    if data:
        df = pd.DataFrame(data)
        df["question_clicked"] = df["question_clicked"].fillna("")
        questions_list = df["question_clicked"].tolist()
        embeddings = embedder.encode(questions_list)
        n_clusters = min(5, len(df))
        kmeans = KMeans(n_clusters=n_clusters, random_state=42)
        df["cluster"] = kmeans.fit_predict(embeddings)
        premium_ml_candidates = df.groupby(["user_id", "cluster"]).size()
        premium_ml_candidates = premium_ml_candidates[
            premium_ml_candidates > 1
        ].reset_index()[["user_id", "cluster"]]
        premium_ml_suggestions = premium_ml_candidates.to_dict(orient="records")
    else:
        premium_ml_suggestions = []

    return jsonify(
        {
            "age_groups": age_groups,
            "jobs": jobs,
            "services": services,
            "questions": questions,
            "desires": desires,
            "premium_suggestions": premium_suggestions,
            "premium_ml_suggestions": premium_ml_suggestions,
        }
    )


# --- Admin engagements & CSV export ---
@app.route("/api/admin/engagements")
@admin_required
def admin_engagements():
    items = []
    for e in eng_col.find().sort("timestamp", -1).limit(500):
        e["_id"] = str(e["_id"])
        e["timestamp"] = e.get("timestamp").isoformat()
        items.append(e)
    return jsonify(items)


@app.route("/api/admin/export_csv")
@admin_required
def export_csv():
    cursor = eng_col.find()

    # Write CSV in text mode
    si = StringIO()
    cw = csv.writer(si)
    cw.writerow(["user_id", "age", "job", "desire", "question", "service", "timestamp"])

    for e in cursor:
        cw.writerow(
            [
                e.get("user_id"),
                e.get("age"),
                e.get("job"),
                ",".join(e.get("desires") or []),
                e.get("question_clicked"),
                e.get("service"),
                e.get("timestamp").isoformat() if e.get("timestamp") else "",
            ]
        )

    # Convert to bytes for send_file
    output = BytesIO()
    output.write(si.getvalue().encode("utf-8"))
    output.seek(0)

    return send_file(
        output, mimetype="text/csv", as_attachment=True, download_name="engagements.csv"
    )


# --- Admin CRUD services ---
@app.route("/api/admin/services", methods=["GET", "POST"], strict_slashes=False)
@admin_required
def admin_services():
    if request.method == "GET":
        return jsonify(list(services_col.find({}, {"_id": 0})))
    payload = request.json
    sid = payload.get("id")
    if not sid:
        return jsonify({"error": "id required"}), 400
    services_col.update_one({"id": sid}, {"$set": payload}, upsert=True)
    return jsonify({"status": "ok"})


@app.route("/api/admin/services/<service_id>", methods=["DELETE"])
@admin_required
def delete_service(service_id):
    services_col.delete_one({"id": service_id})
    return jsonify({"status": "deleted"})


# --- AI search endpoint ---
@app.route("/api/ai/search", methods=["POST"])
@limiter.limit("20/minute")
def search():
    try:
        data = request.get_json()
        query = data.get("query", "").strip()

        if not query:
            return jsonify({"error": "Query required"}), 400

        # --- Embed the query ---
        q_embed = embedder.encode(query)
        q_embed = np.array(q_embed).flatten().tolist()

        # --- Query vector store ---
        results = collection.query(
            query_embeddings=[q_embed],
            n_results=3,
            include=["metadatas", "documents", "distances"],
        )

        print("DEBUG RESULTS FROM CHROMA:", results)  # <--- ADD THIS

        best_answer = "No answer found."
        best_distance = None

        # --- Extract fields safely ---
        metadatas = results.get("metadatas", [])
        documents = results.get("documents", [])
        distances = results.get("distances", [])

        # --- A helper that guarantees the object is list-of-list ---
        def safe_list_of_list(x):
            if isinstance(x, list) and len(x) > 0 and isinstance(x[0], list):
                return x
            return [[]]  # return empty structure instead of int

        metadatas = safe_list_of_list(metadatas)
        documents = safe_list_of_list(documents)
        distances = safe_list_of_list(distances)

        # --- If nothing found, return safely ---
        if len(distances[0]) == 0 or len(documents[0]) == 0:
            return jsonify({"query": query, "answer": best_answer, "distance": None})

        # --- Pick best match ---
        min_idx = int(np.argmin(distances[0]))
        best_distance = distances[0][min_idx]
        doc_str = documents[0][min_idx]

        # --- Parse stored JSON ---
        try:
            doc_data = json.loads(doc_str)
            best_answer = doc_data["subservices"][0]["questions"][0]["answer"]["en"]
        except Exception:
            pass

        return jsonify(
            {"query": query, "answer": best_answer, "distance": best_distance}
        )

    except Exception as e:
        import traceback

        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


# --- Main ---
if __name__ == "__main__":
    if admins_col.count_documents({}) == 0:
        admins_col.insert_one(
            {"username": "admin", "password": os.getenv("ADMIN_PWD", "admin123")}
        )
    app.run(debug=True, host="0.0.0.0", port=int(os.getenv("PORT", 5000)))
