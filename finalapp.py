# app.py — Hybrid FAISS + AI citizen portal (complete)
from flask import Flask, request, jsonify, render_template, session, redirect, url_for, send_file
from flask_cors import CORS
from flask_session import Session
from pymongo import MongoClient
from bson import ObjectId, Binary
from datetime import datetime
import bcrypt
import os
from functools import wraps
import csv
import io
import pathlib
import numpy as np
import json
import logging

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
    "mongodb+srv://amushun1992_db_user:PwQge1UbU41Z3Xjs@tm-users.vxuhp3p.mongodb.net/citizen_portal?retryWrites=true&w=majority"
)

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# ---------------- APP ----------------
app = Flask(__name__, static_folder="static", template_folder="templates")
app.secret_key = os.environ.get("FLASK_SECRET", "prod-secret-key")
app.config["SESSION_TYPE"] = "filesystem"
app.config["SESSION_COOKIE_SECURE"] = os.environ.get(
    "SESSION_COOKIE_SECURE", "False") == "True"
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
                "sentence-transformers not available. Install with `pip install sentence-transformers`")
        # model_name = os.getenv(
        #     "EMBED_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
        model_name = os.getenv(
            "EMBED_MODEL", "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")

        EMBED_MODEL = SentenceTransformer(model_name)
        logger.info(f"Loaded embedding model: {model_name}")
    return EMBED_MODEL


# ---------------- OpenAI helper ----------------
if OPENAI_AVAILABLE and OPENAI_API_KEY:
    openai.api_key = OPENAI_API_KEY


def ask_ai(query):
    """
    Ask OpenAI; returns string answer. If OpenAI not configured, returns None.
    """
    if not OPENAI_AVAILABLE or not OPENAI_API_KEY:
        return None
    try:
        # using chat completion for best short answers
        resp = openai.ChatCompletion.create(
            model=os.getenv("OPENAI_MODEL", "gpt-3.5-turbo"),
            messages=[{"role": "user", "content": query}],
            temperature=0.2,
            max_tokens=512,
        )
        return resp.choices[0].message.content.strip()
    except Exception as e:
        logger.exception("OpenAI call failed: %s", e)
        return None

# ---------------- FAISS index builder & loader ----------------


# def build_faiss_index():
#     if not FAISS_AVAILABLE:
#         logger.warning("FAISS not available; cannot build index.")
#         return False

#     # collect texts + metadata
#     services = list(services_col.find({}, {"_id": 0}))
#     texts = []
#     items = []
#     for service in services:
#         svc_name = service.get("name", {}).get("en", "") or ""
#         for sub in service.get("subservices", []) or []:
#             sub_name = sub.get("name", {}).get("en", "") or ""
#             for q in sub.get("questions", []) or []:
#                 q_text = q.get("q", {}).get("en", "") or ""
#                 combined = " ".join([svc_name, sub_name, q_text]).strip()
#                 texts.append(combined)
#                 items.append({
#                     "service": svc_name,
#                     "subservice": sub_name,
#                     "question": q_text,
#                     "answer": q.get("answer", {}).get("en", "")
#                 })

#     if len(texts) == 0:
#         logger.info("No texts found to index.")
#         return False

#     try:
#         model = get_embedding_model()
#         vectors = model.encode(texts, convert_to_numpy=True)

#         index = faiss.IndexFlatL2(VECTOR_DIM)
#         index.add(vectors)

#         if not INDEX_PATH.parent.exists():
#             INDEX_PATH.parent.mkdir(parents=True, exist_ok=True)

#         faiss.write_index(index, str(INDEX_PATH))
#         with open(META_PATH, "w", encoding="utf-8") as f:
#             json.dump(items, f, indent=2, ensure_ascii=False)

#         logger.info("FAISS index built: %s (%d items)", INDEX_PATH, len(items))
#         return True
#     except Exception as e:
#         logger.exception("Failed to build FAISS index: %s", e)
#         return False

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

                # 🔥 MUST include answer text for proper semantic search
                combined = " ".join([
                    svc_name,
                    sub_name,
                    q_text,
                    a_text
                ]).strip()

                texts.append(combined)

                # Meta item
                items.append({
                    "service": svc_name,
                    "subservice": sub_name,
                    "question": q_text,
                    "answer": a_text
                })

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
        return render_template("main.html")
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
        return render_template("newadmin.html")
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
            "created_at": datetime.utcnow()
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
            {"$set": {
                "email": step_data.get("email"),
                "phone": step_data.get("phone")
            }}
        )
        return jsonify({"status": "ok"})

    if step == "employment":
        profiles_col.update_one(
            {"_id": pid},
            {"$set": {
                "job": step_data.get("job")
            }}
        )
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

# ---------------- Engagement CSV ----------------


@app.route("/api/admin/export_engagement_csv", methods=["GET"])
@admin_required
def export_engagement_csv():
    try:
        cursor = eng_col.find()
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["user_id", "age", "job", "desires", "question_clicked",
                         "service", "ad", "source", "timestamp"])
        for e in cursor:
            writer.writerow([
                e.get("user_id"),
                e.get("age"),
                e.get("job"),
                ",".join(e.get("desires") or []),
                e.get("question_clicked"),
                e.get("service"),
                e.get("ad"),
                e.get("source"),
                e.get("timestamp")
            ])
        output.seek(0)
        return send_file(io.BytesIO(output.getvalue().encode("utf-8")),
                         mimetype="text/csv",
                         as_attachment=True,
                         download_name="engagements.csv")
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

# ---------------- HYBRID SEARCH (FAISS -> OpenAI -> DB text fallback) ----------------
# @app.route("/api/ai/search", methods=["GET", "POST"])
# def api_ai_search():
#     """
#     POST: JSON { query: "...", top_k: 5 }
#     GET: returns simple JSON explaining usage (avoids browser 404 confusion)
#     """
#     if request.method == "GET":
#         return jsonify({"info": "POST JSON {query:'...', top_k:5} to this endpoint"}), 200

#     data = request.get_json(silent=True) or {}
#     query = (data.get("query") or "").strip()
#     top_k = int(data.get("top_k", 5))

#     if not query:
#         return jsonify({"error": "Query required"}), 400

#     # 1) FAISS
#     idx, meta = load_faiss_index()
#     if idx is not None and meta:
#         try:
#             model = get_embedding_model()
#             q_vec = model.encode([query], convert_to_numpy=True)
#             distances, ids = idx.search(q_vec, max(1, top_k))
#             faiss_results = []
#             for i, d in zip(ids[0], distances[0]):
#                 if i != -1 and i < len(meta):
#                     item = meta[i].copy()
#                     item["distance"] = float(d)
#                     faiss_results.append(item)
#             if faiss_results:
#                 return jsonify({"source": "faiss", "query": query, "results": faiss_results})
#         except Exception as e:
#             logger.exception("FAISS search error, falling back: %s", e)

#     # 2) OpenAI fallback (if available)
#     ai_answer = ask_ai(query)
#     if ai_answer:
#         return jsonify({"source": "ai", "query": query, "answer": ai_answer})

#     # 3) Text-based DB fallback (search service names, descriptions, question text)
#     q = {"$regex": query, "$options": "i"}
#     service_hits = list(services_col.find(
#         {"$or": [
#             {"name.en": q},
#             {"name": q},
#             {"description": q},
#         ]},
#         {"_id": 0}
#     ))
#     # scan questions embedded in services (if any)
#     question_hits = []
#     for svc in services_col.find({}, {"_id": 0}):
#         svc_name = svc.get("name", {}).get("en", "")
#         for sub in svc.get("subservices", []) or []:
#             for qobj in sub.get("questions", []) or []:
#                 qtext = qobj.get("q", {}).get("en", "")
#                 if qtext and query.lower() in qtext.lower():
#                     question_hits.append({
#                         "service": svc_name,
#                         "subservice": sub.get("name", {}).get("en", ""),
#                         "question": qtext,
#                         "answer": qobj.get("answer", {}).get("en", "")
#                     })

#     final = service_hits + question_hits
#     return jsonify({"source": "db", "query": query, "results": final})
# //api_ai_search


# @app.route("/api/ai/search", methods=["GET", "POST"])
# def api_ai_search():
#     """
#     Hybrid AI Search
#     Priority:
#     1. FAISS semantic search
#     2. Keyword DB search
#     3. AI answer (OpenAI fallback)
#     GET returns usage info
#     """

#     # ---- GET REQUEST (avoid browser 404) ----
#     if request.method == "GET":
#         return jsonify({
#             "info": "Use POST with JSON: { query: 'text', top_k: 5 }"
#         }), 200

#     # ---- Parse input ----
#     data = request.get_json(silent=True) or {}
#     query = (data.get("query") or "").strip()
#     top_k = int(data.get("top_k", 5))

#     if not query:
#         return jsonify({"error": "Query required"}), 400

#     # ==========================================================
#     # 1️⃣  FAISS SEMANTIC SEARCH (main accurate method)
#     # ==========================================================
#     try:
#         idx, meta = load_faiss_index()
#         if idx is not None and meta:
#             model = get_embedding_model()
#             q_vec = model.encode([query], convert_to_numpy=True)

#             distances, ids = idx.search(q_vec, max(1, top_k))

#             results = []
#             for i, d in zip(ids[0], distances[0]):
#                 if i != -1 and i < len(meta):
#                     item = meta[i].copy()
#                     item["score"] = float(d)
#                     item["source"] = "faiss"
#                     results.append(item)

#             # Return FAISS results if exist
#             if results:
#                 return jsonify({
#                     "source": "faiss",
#                     "query": query,
#                     "results": results
#                 }), 200

#     except Exception as e:
#         app.logger.exception("FAISS error: %s", e)

#     # ==========================================================
#     # 2️⃣  KEYWORD DB FALLBACK
#     # ==========================================================
#     try:
#         q_regex = {"$regex": query, "$options": "i"}

#         # Search services by name & description
#         service_hits = list(services_col.find(
#             {
#                 "$or": [
#                     {"name.en": q_regex},
#                     {"description": q_regex}
#                 ]
#             },
#             {"_id": 0}
#         ))

#         # Search inside Q&A
#         question_hits = []
#         for svc in services_col.find({}, {"_id": 0}):
#             svc_name = svc.get("name", {}).get("en", "")
#             for sub in svc.get("subservices", []) or []:
#                 sub_name = sub.get("name", {}).get("en", "")
#                 for qobj in sub.get("questions", []) or []:
#                     q_text = qobj.get("q", {}).get("en", "")
#                     a_text = qobj.get("answer", {}).get("en", "")

#                     if query.lower() in (q_text + " " + a_text).lower():
#                         question_hits.append({
#                             "service": svc_name,
#                             "subservice": sub_name,
#                             "question": q_text,
#                             "answer": a_text,
#                             "source": "db"
#                         })

#         final_db = service_hits + question_hits

#         if final_db:
#             return jsonify({
#                 "source": "db",
#                 "query": query,
#                 "results": final_db
#             }), 200

#     except Exception as e:
#         app.logger.exception("DB backup search error: %s", e)

#     # ==========================================================
#     # 3️⃣  AI LAST RESORT (only when nothing in FAISS/DB)
#     # ==========================================================
#     try:
#         ai_answer = ask_ai(query)
#         if ai_answer:
#             return jsonify({
#                 "source": "ai",
#                 "query": query,
#                 "answer": ai_answer
#             }), 200
#     except Exception as e:
#         app.logger.exception("AI error: %s", e)

#     # ==========================================================
#     # 4️⃣  NOTHING FOUND
#     # ==========================================================
#     return jsonify({
#         "source": "none",
#         "query": query,
#         "results": [],
#         "message": "No information found in FAISS, database, or AI."
#     }), 200


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

    # 1️⃣ FAISS SEARCH
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
                return jsonify({
                    "source": "faiss",
                    "query": query,
                    "result": item
                }), 200
    except Exception as e:
        app.logger.exception("FAISS error: %s", e)

    # 2️⃣ DB SEARCH (first match only)
    try:
        q_regex = {"$regex": query, "$options": "i"}
        svc = services_col.find_one(
            {"$or": [{"name.en": q_regex}, {"description": q_regex}]},
            {"_id": 0}
        )
        if svc:
            svc["source"] = "db"
            return jsonify({
                "source": "db",
                "query": query,
                "result": svc
            }), 200
    except Exception as e:
        app.logger.exception("DB search error: %s", e)

    # 3️⃣ AI FALLBACK
    try:
        # Build context from DB
        context_docs = []
        for svc in services_col.find({}, {"_id": 0}):
            for sub in svc.get("subservices", []) or []:
                for qobj in sub.get("questions", []) or []:
                    q_text = qobj.get("q", {}).get("en", "")
                    a_text = qobj.get("answer", {}).get("en", "")
                    if q_text and a_text:
                        context_docs.append({"question": q_text, "answer": a_text})

        ai_answer = ask_ai_with_context(query, context_docs=context_docs)
        if ai_answer:
            return jsonify({
                "source": "ai",
                "query": query,
                "result": {
                    "answer": ai_answer,
                    "source": "ai"
                }
            }), 200
    except Exception as e:
        app.logger.exception("AI fallback error: %s", e)

    # 4️⃣ NOTHING FOUND
    return jsonify({
        "source": "none",
        "query": query,
        "result": {
            "answer": "No relevant information found.",
            "source": "hybrid"
        }
    }), 200



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
                        context_docs.append({"question": q_text, "answer": a_text})
    except Exception as e:
        app.logger.exception("Error building context docs: %s", e)

    # ----------------- Query AI -----------------
    try:
        ai_answer = ask_ai_with_context_single(query, context_docs)
        if ai_answer:
            return jsonify({
                "source": "ai",
                "query": query,
                "results": [{
                    "answer": ai_answer,
                    "source": "ai"
                }]
            }), 200
    except Exception as e:
        app.logger.exception("AI error: %s", e)
        return jsonify({
            "source": "ai",
            "query": query,
            "results": [{
                "answer": "AI service unavailable.",
                "source": "ai"
            }]
        }), 200

    # ----------------- NOTHING FOUND -----------------
    return jsonify({
        "source": "ai",
        "query": query,
        "results": [{
            "answer": "No relevant information found.",
            "source": "ai"
        }]
    }), 200


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
