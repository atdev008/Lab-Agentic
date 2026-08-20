# ABC Beverage RAG Chat

AI Chat UI สำหรับถาม-ตอบเกี่ยวกับนโยบายและ SOP ของบริษัท ABC Beverage
ใช้ RAG (Retrieval Augmented Generation) ค้นหาจากเอกสาร PDF ที่เก็บใน Supabase pgvector

## Tech Stack

- **Frontend**: Next.js 14 + Tailwind CSS
- **Backend API**: Python FastAPI (Vercel Serverless Function)
- **Vector Store**: Supabase pgvector
- **Embedding**: Google Gemini (`gemini-embedding-001`)
- **LLM**: Typhoon AI (`typhoon-v2.5-30b-a3b-instruct`)

## โครงสร้างโปรเจค

```
rag-chat/
├── api/
│   └── index.py            # Python API (RAG endpoint)
├── scripts/
│   └── ingest_pdf.py       # Script ingest PDF → Supabase (รันบนเครื่อง)
├── src/
│   └── app/
│       ├── layout.tsx       # Root layout
│       ├── page.tsx         # Chat UI
│       └── globals.css      # Styles
├── .env.example             # ตัวอย่าง environment variables
├── package.json             # Frontend dependencies
├── requirements.txt         # Python dependencies
├── vercel.json              # Vercel deployment config
└── README.md
```

## ขั้นตอนการใช้งาน

### 1. ตั้งค่า Supabase

รัน `setup_supabase.sql` ใน Supabase SQL Editor (อยู่ใน root folder ของโปรเจค)

### 2. สร้างไฟล์ `.env`

```bash
cp .env.example .env
```

แก้ค่าใน `.env` ให้ตรงกับ Supabase project และ API keys ของคุณ

### 3. Ingest PDF (รันครั้งเดียว)

```bash
cd rag-chat
pip install -r requirements.txt pypdf python-dotenv
python scripts/ingest_pdf.py
```

Script จะอ่าน PDF จาก `../ABC_Beverage_RAG_Documents/` → สร้าง embedding → เก็บใน Supabase

### 4. Run Development (Local)

**Terminal 1 — Python API:**
```bash
cd rag-chat
pip install -r requirements.txt
uvicorn api.index:app --reload --port 8000
```

**Terminal 2 — Next.js Frontend:**
```bash
cd rag-chat
npm install
npm run dev
```

เปิด http://localhost:3000

### 5. Deploy ขึ้น Vercel

```bash
# Install Vercel CLI
npm i -g vercel

# Deploy
cd rag-chat
vercel

# ตั้งค่า Environment Variables บน Vercel Dashboard:
# SUPABASE_URL, SUPABASE_KEY, TYPHOON_API_KEY, GEMINI_API_KEY, etc.
```

## Environment Variables

| Variable | Description |
|----------|-------------|
| `SUPABASE_URL` | Supabase project URL |
| `SUPABASE_KEY` | Supabase service role key |
| `TYPHOON_API_KEY` | Typhoon AI API key |
| `TYPHOON_MODEL` | LLM model (default: `typhoon-v2.5-30b-a3b-instruct`) |
| `GEMINI_API_KEY` | Google Gemini API key |
| `GEMINI_EMBEDDING_MODEL` | Embedding model (default: `gemini-embedding-001`) |
| `EMBEDDING_DIMENSIONS` | Vector dimensions (default: `1536`) |

## ตัวอย่างคำถามที่ถามได้

- "ถ้าลูกค้าค้างชำระเกิน 60 วัน ต้องทำอย่างไร?"
- "นโยบายส่วนลดสำหรับลูกค้า VIP มีอะไรบ้าง?"
- "ขั้นตอนการขอลาพักร้อนเป็นอย่างไร?"
- "SOP การตรวจรับสินค้าเข้าคลังคืออะไร?"
- "ขั้นตอนการจัดซื้อสินค้ามีกี่ขั้นตอน?"
