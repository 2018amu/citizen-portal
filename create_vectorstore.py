import os
os.environ["HF_HOME"] = "D:/huggingface_cache" # store in local disk D

from pymongo import MongoClient
import chromadb
from chromadb.utils import embedding_functions
from dotenv import load_dotenv
import json
from bson import ObjectId

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI")
client = MongoClient(MONGO_URI)
db = client["citizen_portal"]
collection_mongo = db["services"]

# Clean MongoDB documents
def clean_doc(doc):
    for k, v in doc.items():
        if isinstance(v, ObjectId):
            doc[k] = str(v)
        elif isinstance(v, list):
            doc[k] = [str(i) if isinstance(i, ObjectId) else i for i in v]
        elif isinstance(v, dict):
            doc[k] = clean_doc(v)
    return doc

# Flatten questions for vector store
docs = []
for doc in collection_mongo.find({}):
    cleaned = clean_doc(doc)
    for sub in cleaned.get("subservices", []):
        for q in sub.get("questions", []):
            question_text = q.get("q", {}).get("en")  # store English question
            answer_text = q.get("answer", {}).get("en")  # store English answer
            if question_text and answer_text:
                docs.append({
                    "id": str(cleaned["_id"]) + "_" + str(sub["id"]) + "_" + str(hash(question_text)),
                    "text": question_text,            # vectorize the question
                    "metadata": {"answer": answer_text}
                })

if not docs:
    raise ValueError("No questions found in MongoDB to build vectorstore.")

# Chroma client with SentenceTransformer embeddings
chroma_client = chromadb.PersistentClient(path="./vectorstore")
embedding_function = embedding_functions.SentenceTransformerEmbeddingFunction(
    model_name="all-MiniLM-L6-v2"
)
collection = chroma_client.get_or_create_collection(
    name="citizen_services",
    embedding_function=embedding_function
)

collection.add(
    documents=[d["text"] for d in docs],
    ids=[d["id"] for d in docs],
    metadatas=[d["metadata"] for d in docs]
)

print("✅ Vectorstore created successfully with questions and answers!")
