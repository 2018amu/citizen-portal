import os, json
from pathlib import Path
from sentence_transformers import SentenceTransformer
import faiss
from bs4 import BeautifulSoup
from PyPDF2 import PdfReader

DATA_DIR = "data"
INDEX_PATH = "data/vector.index"
CHUNKS_PATH = "data/chunks.json"

model = SentenceTransformer("all-MiniLM-L6-v2")

def extract_text_from_pdf(path):
    reader = PdfReader(path)
    pages = []
    for p in reader.pages:
        pages.append(p.extract_text() or "")
    return "\n".join(pages)

def extract_text_from_html(path):
    html = open(path, "r", encoding="utf8").read()
    soup = BeautifulSoup(html, "html.parser")
    return soup.get_text(separator=" ")

def chunk_text(text, size=300):
    words = text.split()
    return [" ".join(words[i:i+size]) for i in range(0, len(words), size)]

def build_vectorstore():
    print("Building vector DB...")

    folder = Path(DATA_DIR)
    folder.mkdir(exist_ok=True)

    files = [str(p) for p in folder.iterdir() if p.suffix.lower() in (".pdf",".html",".htm")]

    if not files:
        print("No PDF/HTML files found in data/.")
        return

    chunks = []
    for f in files:
        if f.endswith(".pdf"):
            text = extract_text_from_pdf(f)
        else:
            text = extract_text_from_html(f)

        for i, ch in enumerate(chunk_text(text)):
            chunks.append({"source": f, "text": ch})

    embeddings = model.encode([c["text"] for c in chunks], convert_to_numpy=True)
    dim = embeddings.shape[1]
    index = faiss.IndexFlatL2(dim)
    index.add(embeddings.astype("float32"))

    faiss.write_index(index, INDEX_PATH)
    json.dump(chunks, open(CHUNKS_PATH, "w", encoding="utf8"), indent=2)

    print("✔ Vector DB generated successfully!")

if __name__ == "__main__":
    build_vectorstore()
