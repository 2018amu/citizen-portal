Citizen Portal******

A web-based portal to browse citizen services, ask AI questions, and track user engagement. Includes a professional admin dashboard for analytics.

Features....

Multi-language citizen services portal (en, si, ta)

View services, subservices, and questions

Optional AI-powered search for questions (/api/ai/search)

Track user engagement (age, job, interests, questions clicked)

Admin dashboard with charts and CSV export

Secure admin login with session-based authentication

Rate-limited API endpoints using Flask-Limiter

---------------Setup-----------------

Clone repo:

git clone <repo_url>
cd <repo_folder>


------------Create virtual environment and install dependencies:------------

python -m venv venv
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate     # Windows

pip install -r requirements.txt


------------Setup environment variables in .env:-----------

OPENAI_API_KEY=openai_key
MONGO_URI=mongo_uri
FLASK_SECRET=flask_secret
ADMIN_PWD=admin123
PORT=5000


----------Run Flask app:------------

python app.py


Frontend: http://localhost:5000

Admin: http://localhost:5000/admin/login

-------Admin Login-----------


Username: admin
Password: admin123


---------Login sends JSON to /admin/login.-----------

After login, dashboard fetches insights from /api/admin/insights.

API Endpoints
Public

/api/services - Get all services

/api/service/<service_id> - Get a single service

/api/engagement (POST) - Log user engagement

AI

/api/ai/search (POST) - Send {"query": "ask a  question"} to get AI answer

Admin

/api/admin/insights - Get analytics data

/api/admin/engagements - List recent engagements

/api/admin/export_csv - Download engagements as CSV

/api/admin/services (GET, POST) - Manage services

/api/admin/services/<id> (DELETE) - Delete a service

/api/admin/logout (POST) - Logout admin

-----Notes------

Ensure Flask-Limiter and sentence-transformers are installed.

Admin password is stored in plain text for demo; production should hash passwords.

AI search uses SentenceTransformer embeddings stored in ChromaDB.