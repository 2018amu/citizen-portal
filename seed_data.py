from pymongo import MongoClient
from dotenv import load_dotenv
import os
import json

# Load environment variables from .env
load_dotenv()

# Get MongoDB URI from environment variable
MONGO_URI = os.getenv("MONGO_URI")
if not MONGO_URI:
    raise ValueError("MONGO_URI not set in environment variables")

# Connect to MongoDB Atlas
client = MongoClient(MONGO_URI)
db = client["citizen_portal"]
services_col = db["services"]

# Clear existing documents
services_col.delete_many({})

# Seed data
docs = [
    {
        "id": "ministry_it",
        "name": {
            "en": "Ministry of IT & Digital Affairs",
            "si": "තොරතුරු තාක්ෂණ අමාත්‍යාංශය",
            "ta": "தகவல் தொழில்நுட்ப அமைச்சு"
        },
        "subservices": [
            {
                "id": "it_cert",
                "name": {
                    "en": "IT Certificates",
                    "si": "අයිටී සහතික",
                    "ta": "ஐடி சான்றிதழ்கள்"
                },
                "questions": [
                    {
                        "q": {
                            "en": "How to apply for an IT certificate?",
                            "si": "IT සහතිකය සඳහා ඉල්ලීම් කරන ආකාරය?",
                            "ta": "ஐடி சான்றிதழுக்கு விண்ணப்பிப்பது எப்படி?"
                        },
                        "answer": {
                            "en": "Fill online form and upload NIC.",
                            "si": "ඔන්ලයින් පෝරම පිරවුවොත් NIC උඩුගත කරන්න.",
                            "ta": "ஆன்லைன் படிவத்தை நிரப்பி NIC ஐ பதிவேற்றவும்."
                        },
                        "downloads": ["/static/forms/it_cert_form.pdf"],
                        "location": "https://maps.google.com/?q=Ministry+of+IT",
                        "instructions": "Visit the digital portal, register and submit application."
                    }
                ]
            }
        ]
    },
    {
        "id": "ministry_education",
        "name": {
            "en": "Ministry of Education",
            "si": "අධ්‍යාපන අමාත්‍යාංශය",
            "ta": "கல்வி அமைச்சு"
        },
        "subservices": [
            {
                "id": "schools",
                "name": {
                    "en": "Schools",
                    "si": "පාසල්",
                    "ta": "பள்ளிகள்"
                },
                "questions": [
                    {
                        "q": {
                            "en": "How to register a school?",
                            "si": "පාසලක් ලියාපදිංචි කිරීම?",
                            "ta": "பள்ளியை பதிவு செய்வது எப்படி?"
                        },
                        "answer": {
                            "en": "Complete registration form and submit documents.",
                            "si": "ලියාපදිංචි පෝරමය පුරවා ලේඛන සලසන්න.",
                            "ta": "பதிவு படிவத்தை பூர்த்தி செய்து ஆவணங்களை சமர்ப்பிக்கவும்."
                        },
                        "downloads": ["/static/forms/school_reg.pdf"],
                        "location": "https://maps.google.com/?q=Ministry+of+Education",
                        "instructions": "Follow the guidelines on the education portal."
                    }
                ]
            }
        ]
    }
]

# Add remaining ministries (minimal example to reach 20)
rest = [
    "ministry_health", "ministry_transport", "ministry_imm",
    "ministry_foreign", "ministry_finance", "ministry_labour",
    "ministry_public", "ministry_justice", "ministry_housing",
    "ministry_agri", "ministry_youth", "ministry_defence",
    "ministry_tourism", "ministry_trade", "ministry_energy",
    "ministry_water", "ministry_env", "ministry_culture"
]

for mid in rest:
    docs.append({
        "id": mid,
        "name": {"en": mid, "si": mid, "ta": mid},
        "subservices": [
            {
                "id": "general",
                "name": {"en": "General Services", "si": "සාමාන්‍ය සේවාවන්", "ta": "பொது சேவைகள்"},
                "questions": [
                    {
                        "q": {"en": "What services are offered?", "si": "ඔබට ලබා දිය හැකි සේවාවන් මොනවාද?", "ta": "எந்த சேவைகள் வழங்கப்படுகின்றன?"},
                        "answer": {"en": "Please check the service list on the portal.", "si": "පෝර්ටලයේ සේවා ලැයිස්තුව බලන්න.", "ta": "போர்ட்டலில் சேவை பட்டியலைப் பார்க்கவும்."},
                        "downloads": [],
                        "location": "",
                        "instructions": "Use contact details to get more info."
                    }
                ]
            }
        ]
    })

# Insert into MongoDB
services_col.insert_many(docs)

print("Seeded services:", services_col.count_documents({}))
