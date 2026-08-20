"""
PDF Ingestion Script — Run once locally to embed PDFs into Supabase pgvector.

Usage:
    cd rag-chat
    pip install -r requirements.txt pypdf
    python scripts/ingest_pdf.py

Make sure .env is configured with:
    SUPABASE_URL, SUPABASE_KEY, GEMINI_API_KEY, GEMINI_EMBEDDING_MODEL
"""

import os
import re
import sys
import time
from pathlib import Path

from dotenv import load_dotenv
from supabase import create_client
from google import genai
from pypdf import PdfReader

# ─── Load Config ──────────────────────────────────────────────────────────────

# Load .env from the rag-chat folder (parent of scripts/)
ENV_PATH = Path(__file__).resolve().parent.parent / ".env"
print(f"Loading .env from: {ENV_PATH}")
print(f".env exists: {ENV_PATH.exists()}")

load_dotenv(ENV_PATH, override=True)

SUPABASE_URL = os.getenv("SUPABASE_URL", "").strip()
SUPABASE_KEY = (
    os.getenv("SUPABASE_SECRET_KEY", "")
    or os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
    or os.getenv("SUPABASE_KEY", "")
).strip()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
GEMINI_EMBEDDING_MODEL = os.getenv("GEMINI_EMBEDDING_MODEL", "gemini-embedding-001").strip()
EMBEDDING_DIMENSIONS = int(os.getenv("EMBEDDING_DIMENSIONS", "1536"))

# Debug: show what was loaded (masked)
print(f"SUPABASE_URL: {SUPABASE_URL[:30]}..." if SUPABASE_URL else "SUPABASE_URL: EMPTY!")
print(f"SUPABASE_KEY: {SUPABASE_KEY[:10]}...({len(SUPABASE_KEY)} chars)" if SUPABASE_KEY else "SUPABASE_KEY: EMPTY!")
print(f"GEMINI_API_KEY: {GEMINI_API_KEY[:10]}..." if GEMINI_API_KEY else "GEMINI_API_KEY: EMPTY!")

assert SUPABASE_URL, "Missing SUPABASE_URL"
assert SUPABASE_KEY, "Missing SUPABASE_KEY"
assert GEMINI_API_KEY, "Missing GEMINI_API_KEY"

try:
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    print("✅ Supabase client created")
except Exception as e:
    print(f"\n❌ Failed to create Supabase client: {e}")
    print("\nTrying alternative: direct REST API approach...")
    # If SDK fails, we'll use direct REST API
    supabase = None
gemini_client = genai.Client(api_key=GEMINI_API_KEY)


# ─── REST API Fallback (if SDK rejects the key) ──────────────────────────────

import httpx


def supabase_rest_delete(table: str, column: str, value: str):
    """Delete rows via Supabase REST API."""
    url = f"{SUPABASE_URL}/rest/v1/{table}?{column}=eq.{value}"
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=minimal",
    }
    r = httpx.delete(url, headers=headers)
    r.raise_for_status()


def supabase_rest_insert(table: str, rows: list[dict]):
    """Insert rows via Supabase REST API."""
    url = f"{SUPABASE_URL}/rest/v1/{table}"
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=minimal",
    }
    r = httpx.post(url, headers=headers, json=rows, timeout=30)
    r.raise_for_status()

# ─── PDF Directory ────────────────────────────────────────────────────────────

PDF_DIR = Path(__file__).resolve().parent.parent.parent / "ABC_Beverage_RAG_Documents"

if not PDF_DIR.exists():
    print(f"❌ PDF directory not found: {PDF_DIR}")
    sys.exit(1)


# ─── Helper Functions ─────────────────────────────────────────────────────────

def normalize_text(text: str) -> str:
    text = text.replace("\x00", " ")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def extract_pdf_text(pdf_path: Path) -> str:
    reader = PdfReader(str(pdf_path))
    pages = []
    for page_number, page in enumerate(reader.pages, start=1):
        page_text = normalize_text(page.extract_text() or "")
        if page_text:
            pages.append(f"[Page {page_number}] {page_text}")
    return "\n".join(pages)


def chunk_text(text: str, chunk_size: int = 900, overlap: int = 150) -> list[str]:
    text = normalize_text(text)
    if not text:
        return []

    chunks = []
    start = 0

    while start < len(text):
        end = min(start + chunk_size, len(text))

        if end < len(text):
            window = text[start:end]
            best = max(
                window.rfind("\n"),
                window.rfind("。"),
                window.rfind(". "),
                window.rfind(" "),
            )
            if best > chunk_size * 0.60:
                end = start + best + 1

        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)

        if end >= len(text):
            break

        start = max(end - overlap, start + 1)

    return chunks


def embed_text(text: str) -> list[float]:
    response = gemini_client.models.embed_content(
        model=GEMINI_EMBEDDING_MODEL,
        contents=text,
        config={"output_dimensionality": EMBEDDING_DIMENSIONS},
    )
    return response.embeddings[0].values


def batched(items: list, size: int = 20):
    for i in range(0, len(items), size):
        yield items[i : i + size]


# ─── Ingest ───────────────────────────────────────────────────────────────────

def ingest_pdf(pdf_path: Path):
    print(f"\n📄 Processing: {pdf_path.name}")

    text = extract_pdf_text(pdf_path)
    chunks = chunk_text(text)
    print(f"   Chunks: {len(chunks)}")

    # Delete old chunks for this file
    if supabase:
        supabase.table("knowledge_documents").delete().eq(
            "source_file", pdf_path.name
        ).execute()
    else:
        try:
            supabase_rest_delete("knowledge_documents", "source_file", pdf_path.name)
        except Exception as e:
            print(f"   ⚠️ Delete warning: {e}")

    rows = []
    for idx, chunk in enumerate(chunks):
        embedding = embed_text(chunk)
        rows.append(
            {
                "title": pdf_path.stem.replace("_", " "),
                "source_file": pdf_path.name,
                "storage_path": f"rag/{pdf_path.name}",
                "chunk_index": idx,
                "content": chunk,
                "metadata": {
                    "file_name": pdf_path.name,
                    "chunk_index": idx,
                    "embedding_model": GEMINI_EMBEDDING_MODEL,
                },
                "embedding": embedding,
            }
        )
        print(f"   ✓ Embedded chunk {idx + 1}/{len(chunks)}")
        time.sleep(0.3)  # Rate limit protection

    # Insert in batches
    for batch in batched(rows, 20):
        if supabase:
            supabase.table("knowledge_documents").insert(batch).execute()
        else:
            supabase_rest_insert("knowledge_documents", batch)

    print(f"   ✅ Inserted {len(rows)} chunks for {pdf_path.name}")


def main():
    pdf_files = sorted(PDF_DIR.glob("*.pdf"))
    print(f"Found {len(pdf_files)} PDF files in {PDF_DIR}")

    for pdf_path in pdf_files:
        ingest_pdf(pdf_path)

    print("\n🎉 All PDFs ingested successfully!")


if __name__ == "__main__":
    main()
