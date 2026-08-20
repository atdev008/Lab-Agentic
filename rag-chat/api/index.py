"""
RAG + SQL Chat API — FastAPI serverless function for Vercel.
Uses Supabase (pgvector + PostgreSQL) + Gemini Embedding + Typhoon LLM.

Supports:
- RAG: search PDF knowledge (policies, SOPs)
- SQL: query structured data (invoices, customers, inventory, etc.)
- Mixed: combine both for complex questions
"""

import os
import json
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from supabase import create_client
from openai import OpenAI
from google import genai

# Load .env for local development
load_dotenv(Path(__file__).resolve().parent.parent / ".env", override=True)

# ─── Configuration ────────────────────────────────────────────────────────────

SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = (
    os.environ.get("SUPABASE_SECRET_KEY", "")
    or os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
    or os.environ.get("SUPABASE_KEY", "")
)

TYPHOON_API_KEY = os.environ.get("TYPHOON_API_KEY", "")
TYPHOON_MODEL = os.environ.get("TYPHOON_MODEL", "typhoon-v2.5-30b-a3b-instruct")

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_EMBEDDING_MODEL = os.environ.get("GEMINI_EMBEDDING_MODEL", "gemini-embedding-001")
EMBEDDING_DIMENSIONS = int(os.environ.get("EMBEDDING_DIMENSIONS", "1536"))

# ─── Clients ──────────────────────────────────────────────────────────────────

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

typhoon_client = OpenAI(
    api_key=TYPHOON_API_KEY,
    base_url="https://api.opentyphoon.ai/v1",
)

gemini_client = genai.Client(api_key=GEMINI_API_KEY)

# ─── FastAPI App ──────────────────────────────────────────────────────────────

app = FastAPI(title="ABC Beverage RAG + SQL Chat")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─── Models ───────────────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    message: str
    history: list[dict] = []


class ChatResponse(BaseModel):
    answer: str
    sources: list[dict] = []
    tools_used: list[str] = []


# ─── SQL Tool Functions ───────────────────────────────────────────────────────

def get_overdue_invoices(customer_name: str = None, min_overdue_days: int = 1, limit: int = 20):
    """Get overdue invoice data from Supabase."""
    query = (
        supabase.table("invoices")
        .select(
            "invoice_no,customer_code,customer_name,invoice_date,due_date,"
            "amount_thb,paid_amount_thb,outstanding_thb,status,overdue_days"
        )
        .gt("outstanding_thb", 0)
        .gte("overdue_days", int(min_overdue_days))
        .order("overdue_days", desc=True)
        .limit(int(limit))
    )
    if customer_name:
        query = query.ilike("customer_name", f"%{customer_name}%")
    result = query.execute()
    return result.data or []


def get_low_stock(limit: int = 50):
    """Get inventory items that need reorder."""
    result = (
        supabase.table("inventory")
        .select("sku,warehouse,quantity_on_hand,minimum_stock,stock_status")
        .eq("stock_status", "REORDER")
        .limit(int(limit))
        .execute()
    )
    return result.data or []


def get_customer(customer_name: str):
    """Get customer master data."""
    result = (
        supabase.table("customers")
        .select(
            "customer_code,customer_name,customer_type,province,"
            "credit_term_days,credit_limit_thb,risk_level,status"
        )
        .ilike("customer_name", f"%{customer_name}%")
        .limit(10)
        .execute()
    )
    return result.data or []


def get_all_customers():
    """Get all customers."""
    result = supabase.table("customers").select("*").execute()
    return result.data or []


def get_products():
    """Get all products."""
    result = supabase.table("products").select("*").execute()
    return result.data or []


def get_employees():
    """Get all employees."""
    result = supabase.table("employees").select("*").execute()
    return result.data or []


def get_invoices_by_customer(customer_name: str = None, limit: int = 40):
    """Get all invoices for a customer."""
    query = supabase.table("invoices").select("*").order("invoice_date", desc=True).limit(int(limit))
    if customer_name:
        query = query.ilike("customer_name", f"%{customer_name}%")
    result = query.execute()
    return result.data or []


# ─── RAG Functions ────────────────────────────────────────────────────────────

def embed_text(text: str) -> list[float]:
    """Create embedding using Gemini."""
    response = gemini_client.models.embed_content(
        model=GEMINI_EMBEDDING_MODEL,
        contents=text,
        config={"output_dimensionality": EMBEDDING_DIMENSIONS},
    )
    return response.embeddings[0].values


def semantic_search(question: str, match_count: int = 5, match_threshold: float = 0.30):
    """Search knowledge documents using pgvector similarity."""
    query_embedding = embed_text(question)
    response = supabase.rpc(
        "match_documents",
        {
            "query_embedding": query_embedding,
            "match_threshold": match_threshold,
            "match_count": match_count,
        },
    ).execute()
    return response.data or []


# ─── Tool Definitions for LLM ────────────────────────────────────────────────

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_overdue_invoices",
            "description": (
                "ดึงข้อมูล Invoice ที่ค้างชำระ ใช้เมื่อถามเรื่องยอดค้าง, วันครบกำหนด, overdue"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "customer_name": {
                        "type": ["string", "null"],
                        "description": "ชื่อลูกค้า (optional filter)"
                    },
                    "min_overdue_days": {
                        "type": "integer",
                        "description": "จำนวนวันขั้นต่ำที่ค้างชำระ"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "จำนวนผลลัพธ์สูงสุด"
                    }
                },
                "required": ["customer_name", "min_overdue_days", "limit"],
                "additionalProperties": False
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_low_stock",
            "description": "ดึงข้อมูลสินค้าที่ Stock ต่ำกว่า minimum ต้อง reorder",
            "parameters": {
                "type": "object",
                "properties": {
                    "limit": {"type": "integer"}
                },
                "required": ["limit"],
                "additionalProperties": False
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_customer",
            "description": "ดึงข้อมูลลูกค้า (credit limit, risk level, สถานะ)",
            "parameters": {
                "type": "object",
                "properties": {
                    "customer_name": {"type": "string"}
                },
                "required": ["customer_name"],
                "additionalProperties": False
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_all_customers",
            "description": "ดึงข้อมูลลูกค้าทั้งหมด",
            "parameters": {
                "type": "object",
                "properties": {},
                "additionalProperties": False
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_products",
            "description": "ดึงข้อมูลสินค้าทั้งหมด (ราคา, หมวดหมู่)",
            "parameters": {
                "type": "object",
                "properties": {},
                "additionalProperties": False
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_employees",
            "description": "ดึงข้อมูลพนักงานทั้งหมด (แผนก, ตำแหน่ง, เงินเดือน)",
            "parameters": {
                "type": "object",
                "properties": {},
                "additionalProperties": False
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_invoices_by_customer",
            "description": "ดึง Invoice ทั้งหมดของลูกค้า (ดูว่าลูกค้าซื้อเท่าไหร่ ชำระแล้วเท่าไหร่)",
            "parameters": {
                "type": "object",
                "properties": {
                    "customer_name": {
                        "type": ["string", "null"],
                        "description": "ชื่อลูกค้า (ถ้าไม่ระบุจะดึงทั้งหมด)"
                    },
                    "limit": {"type": "integer"}
                },
                "required": ["customer_name", "limit"],
                "additionalProperties": False
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_company_knowledge",
            "description": (
                "ค้นหาเอกสาร PDF (นโยบาย, SOP, ระเบียบ) ของบริษัท ใช้เมื่อถามเรื่อง policy, "
                "ขั้นตอนการทำงาน, กฎระเบียบ, สิทธิ์การลา, เงื่อนไขส่วนลด"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "question": {"type": "string"},
                    "match_count": {"type": "integer"}
                },
                "required": ["question", "match_count"],
                "additionalProperties": False
            }
        }
    },
]

# Tool router
TOOL_FUNCTIONS = {
    "get_overdue_invoices": get_overdue_invoices,
    "get_low_stock": get_low_stock,
    "get_customer": get_customer,
    "get_all_customers": get_all_customers,
    "get_products": get_products,
    "get_employees": get_employees,
    "get_invoices_by_customer": get_invoices_by_customer,
    "search_company_knowledge": lambda question, match_count=5: semantic_search(question, int(match_count)),
}


# ─── Agent Loop ───────────────────────────────────────────────────────────────

AGENT_SYSTEM_PROMPT = """คุณคือ AI Agent ของบริษัท ABC Beverage Co., Ltd.

Tools ที่มี:
- get_overdue_invoices: ดึง Invoice ค้างชำระ
- get_low_stock: ดูสินค้า stock ต่ำ
- get_customer / get_all_customers: ข้อมูลลูกค้า
- get_products: ข้อมูลสินค้า
- get_employees: ข้อมูลพนักงาน
- get_invoices_by_customer: ดึง Invoice ของลูกค้า (ไม่ระบุชื่อ = ดึงทั้งหมด)
- search_company_knowledge: ค้นหา policy/SOP จาก PDF

กฎสำคัญ:
1. เรียก tool น้อยที่สุดเท่าที่จำเป็น ถ้าต้องการข้อมูลรวมให้ใช้ tool 1 ครั้งแล้วสรุปผล
2. get_invoices_by_customer ถ้าไม่ระบุ customer_name=null จะดึง invoice ทั้งหมดได้ในครั้งเดียว
3. ตอบกระชับ ตรงประเด็น
4. ถ้าไม่มีข้อมูลที่ตรงคำถาม ให้บอกตรงๆ ว่า "ข้อมูลนี้ไม่มีในระบบ"
5. ตอบเป็นภาษาไทย
6. ห้ามเดาตัวเลข ต้องมาจาก tool เท่านั้น
7. ข้อมูลที่มีเป็น Invoice (ยอดเงิน) ไม่มีรายละเอียดสินค้าที่สั่งซื้อ"""


def run_agent(message: str, history: list[dict], max_rounds: int = 4):
    """Run agent loop with tool calling."""
    messages = [{"role": "system", "content": AGENT_SYSTEM_PROMPT}]

    # Add conversation history
    for h in history[-10:]:
        messages.append({"role": h.get("role", "user"), "content": h.get("content", "")})

    messages.append({"role": "user", "content": message})

    tools_used = []
    sources = []

    for _ in range(max_rounds):
        response = typhoon_client.chat.completions.create(
            model=TYPHOON_MODEL,
            messages=messages,
            tools=TOOLS,
            tool_choice="auto",
            temperature=0.2,
            max_tokens=2000,
        )

        assistant_message = response.choices[0].message
        messages.append(assistant_message.model_dump(exclude_none=True))

        tool_calls = assistant_message.tool_calls or []

        # No tool calls = final answer
        if not tool_calls:
            answer = assistant_message.content or ""
            if not answer:
                # Force a final answer without tools
                messages.append({
                    "role": "user",
                    "content": "กรุณาสรุปคำตอบจากข้อมูลที่ได้มาทั้งหมด"
                })
                final_resp = typhoon_client.chat.completions.create(
                    model=TYPHOON_MODEL,
                    messages=messages,
                    temperature=0.2,
                    max_tokens=2000,
                )
                answer = final_resp.choices[0].message.content or "ไม่สามารถประมวลผลได้"
            return answer, sources, tools_used

        for call in tool_calls:
            tool_name = call.function.name
            arguments = json.loads(call.function.arguments or "{}")

            tools_used.append(tool_name)

            # Execute tool
            func = TOOL_FUNCTIONS.get(tool_name)
            if func:
                try:
                    result = func(**arguments)
                except Exception as e:
                    result = {"error": str(e)}
            else:
                result = {"error": f"Unknown tool: {tool_name}"}

            # Track sources for RAG
            if tool_name == "search_company_knowledge" and isinstance(result, list):
                for r in result:
                    sources.append({
                        "file": r.get("source_file", ""),
                        "similarity": round(r.get("similarity", 0), 4),
                    })

            messages.append({
                "role": "tool",
                "tool_call_id": call.id,
                "content": json.dumps(result, ensure_ascii=False, default=str)
            })

    return "Agent exceeded maximum rounds", sources, tools_used


# ─── API Routes ───────────────────────────────────────────────────────────────

@app.get("/api/health")
def health():
    return {"status": "ok", "model": TYPHOON_MODEL}


@app.post("/api/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    if not req.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty")

    try:
        answer, sources, tools_used = run_agent(req.message, req.history)
        return ChatResponse(answer=answer, sources=sources, tools_used=tools_used)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
