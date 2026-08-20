# 🚀 คู่มือ Deploy ขึ้น Vercel — ABC Beverage RAG Chat

## สิ่งที่ต้องเตรียมก่อน Deploy

### 1. Supabase (ทำครั้งเดียว)

- [ ] สร้าง Supabase Project
- [ ] รัน `setup_supabase.sql` ใน SQL Editor (สร้างตาราง + pgvector)
- [ ] รัน `python scripts/ingest_excel.py` บนเครื่อง (อัปโหลดข้อมูล Excel)
- [ ] รัน `python scripts/ingest_pdf.py` บนเครื่อง (อัปโหลด PDF embeddings)

### 2. API Keys ที่ต้องมี

| Key | ที่มา |
|-----|-------|
| `SUPABASE_URL` | Supabase Dashboard → Settings → API → Project URL |
| `SUPABASE_KEY` | Supabase Dashboard → Settings → API → service_role key |
| `TYPHOON_API_KEY` | https://opentyphoon.ai → สร้าง API key |
| `GEMINI_API_KEY` | https://aistudio.google.com/apikey → สร้าง API key |

---

## Python Libraries (สำหรับ Vercel Serverless Function)

ไฟล์ `requirements.txt`:

```
fastapi==0.115.0
uvicorn==0.30.0
supabase==2.9.0
openai==1.52.0
google-genai==1.0.0
python-dotenv==1.0.1
```

> Vercel จะอ่าน `requirements.txt` อัตโนมัติสำหรับ Python runtime

---

## Node.js Libraries (สำหรับ Frontend)

ไฟล์ `package.json` → ติดตั้งด้วย `npm install`:

```
next          ^14.2.0     — React framework
react         ^18.3.0     — UI library
react-dom     ^18.3.0     — React DOM renderer
tailwindcss   ^3.4.0      — CSS framework
typescript    ^5.4.0      — Type checking
autoprefixer  ^10.4.0     — PostCSS plugin
postcss       ^8.4.0      — CSS processor
```

---

## ขั้นตอน Deploy

### วิธี A: ผ่าน GitHub (แนะนำ)

```bash
# 1. เข้า folder
cd rag-chat

# 2. Init git
git init
git add .
git commit -m "ABC Beverage RAG Chat"

# 3. สร้าง repo บน GitHub แล้ว push
git remote add origin https://github.com/YOUR_USER/rag-chat.git
git branch -M main
git push -u origin main

# 4. ไปที่ vercel.com
#    → New Project
#    → Import Git Repository (เลือก rag-chat)
#    → Framework: Next.js (จะ detect อัตโนมัติ)
#    → ตั้ง Environment Variables (ดูด้านล่าง)
#    → Deploy
```

### วิธี B: ผ่าน Vercel CLI

```bash
# 1. ติดตั้ง Vercel CLI
npm i -g vercel

# 2. Login
vercel login

# 3. Deploy
cd rag-chat
vercel

# ตอบคำถาม:
#   Set up and deploy? → Y
#   Which scope? → เลือก account
#   Link to existing project? → N
#   Project name? → abc-beverage-rag-chat
#   Directory? → ./
#   Override settings? → N

# 4. Deploy production
vercel --prod
```

---

## ตั้งค่า Environment Variables บน Vercel

ไปที่ **Vercel Dashboard → Project → Settings → Environment Variables**

เพิ่มทั้งหมดนี้:

```
SUPABASE_URL=https://xxxxx.supabase.co
SUPABASE_KEY=eyJhbGciOiJIUzI1NiIs...  (service_role key)
TYPHOON_API_KEY=sk-xxxxx
TYPHOON_MODEL=typhoon-v2.5-30b-a3b-instruct
GEMINI_API_KEY=xxxxx
GEMINI_EMBEDDING_MODEL=gemini-embedding-001
EMBEDDING_DIMENSIONS=1536
NEXT_PUBLIC_API_URL=
```

> `NEXT_PUBLIC_API_URL` ปล่อยว่างตอนแรก — หลัง deploy จะได้ URL เช่น `https://abc-beverage-rag-chat.vercel.app` ให้ใส่ URL นั้นกลับเข้าไป

**สำคัญ**: หลัง deploy ครั้งแรก ต้องอัปเดต `NEXT_PUBLIC_API_URL` ให้ตรงกับ URL ของ project แล้ว redeploy อีกครั้ง

---

## ไฟล์สำคัญที่ Vercel ใช้

| ไฟล์ | Vercel ใช้ทำอะไร |
|------|-----------------|
| `vercel.json` | Config routing + Python runtime |
| `requirements.txt` | ติดตั้ง Python packages สำหรับ API |
| `package.json` | ติดตั้ง Node packages + build Next.js |
| `api/index.py` | Python Serverless Function (endpoint `/api/*`) |

---

## vercel.json (สำคัญ)

```json
{
  "buildCommand": "npm run build",
  "outputDirectory": ".next",
  "rewrites": [
    {
      "source": "/api/(.*)",
      "destination": "/api/index.py"
    }
  ],
  "functions": {
    "api/index.py": {
      "runtime": "python3.11",
      "maxDuration": 30
    }
  }
}
```

---

## หลัง Deploy สำเร็จ

URL ที่ได้ เช่น: `https://abc-beverage-rag-chat.vercel.app`

1. อัปเดต `NEXT_PUBLIC_API_URL` = `https://abc-beverage-rag-chat.vercel.app`
2. Redeploy (Vercel Dashboard → Deployments → Redeploy)
3. เปิด URL → ใช้งาน Chat ได้เลย

---

## Troubleshooting

| ปัญหา | แก้ไข |
|-------|------|
| API timeout | Vercel free plan มี 10s timeout → อัปเกรดเป็น Pro (60s) หรือ ลองใช้ Typhoon model เร็วกว่า |
| 500 error | เช็ค Vercel → Function Logs ว่า error อะไร (มักเป็น env var หาย) |
| CORS error | ตรวจว่า `NEXT_PUBLIC_API_URL` ตรงกับ domain จริง |
| "Invalid API key" | ตรวจว่า SUPABASE_KEY เป็น JWT (ขึ้นต้น eyJ...) |

---

## Libraries สำหรับรัน Scripts บนเครื่อง (ไม่เกี่ยวกับ Vercel)

ใช้ตอนรัน `ingest_pdf.py` และ `ingest_excel.py` บนเครื่อง:

```bash
pip install python-dotenv supabase google-genai pypdf pandas openpyxl
```
