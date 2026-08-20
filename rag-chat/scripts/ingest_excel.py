"""
Excel Ingestion Script — Upload Excel data to Supabase PostgreSQL.

Usage:
    cd rag-chat
    python scripts/ingest_excel.py

Make sure:
    1. .env is configured
    2. setup_supabase.sql has been run in Supabase SQL Editor
"""

import os
import sys
from pathlib import Path
from typing import Any

import pandas as pd
from dotenv import load_dotenv
from supabase import create_client

# ─── Load Config ──────────────────────────────────────────────────────────────

ENV_PATH = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(ENV_PATH, override=True)

SUPABASE_URL = os.getenv("SUPABASE_URL", "").strip()
SUPABASE_KEY = (
    os.getenv("SUPABASE_SECRET_KEY", "")
    or os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
    or os.getenv("SUPABASE_KEY", "")
).strip()

assert SUPABASE_URL, "Missing SUPABASE_URL"
assert SUPABASE_KEY, "Missing SUPABASE_KEY"

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# ─── Excel Path ───────────────────────────────────────────────────────────────

EXCEL_PATH = Path(__file__).resolve().parent.parent.parent / "ABC_Beverage_Agentic_AI_Training_Dataset.xlsx"

if not EXCEL_PATH.exists():
    print(f"❌ Excel file not found: {EXCEL_PATH}")
    sys.exit(1)

# ─── Config ───────────────────────────────────────────────────────────────────

SHEET_CONFIG = {
    "Customers": ("customers", "customer_code"),
    "Products": ("products", "sku"),
    "Inventory": ("inventory", "sku,warehouse"),
    "Invoices": ("invoices", "invoice_no"),
    "Payments": ("payments", "payment_no"),
    "Employees": ("employees", "employee_code"),
}

DATE_COLUMNS = {
    "Invoices": ["invoice_date", "due_date"],
    "Payments": ["payment_date"],
    "Employees": ["start_date"],
}

INT_COLUMNS = {
    "Customers": ["credit_term_days"],
    "Products": ["minimum_stock"],
    "Inventory": ["quantity_on_hand", "minimum_stock"],
    "Invoices": ["overdue_days"],
}


# ─── Helpers ──────────────────────────────────────────────────────────────────

def json_safe(value: Any) -> Any:
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except Exception:
        pass
    if isinstance(value, pd.Timestamp):
        if value.hour == 0 and value.minute == 0 and value.second == 0:
            return value.date().isoformat()
        return value.isoformat()
    if hasattr(value, "item"):
        try:
            return value.item()
        except Exception:
            pass
    return value


def dataframe_records(df: pd.DataFrame) -> list[dict]:
    return [
        {str(k): json_safe(v) for k, v in row.items()}
        for row in df.to_dict(orient="records")
    ]


def batched(items: list, size: int = 100):
    for i in range(0, len(items), size):
        yield items[i : i + size]


# ─── Upload ───────────────────────────────────────────────────────────────────

def load_excel_to_supabase():
    print(f"📊 Loading: {EXCEL_PATH.name}")

    for sheet_name, (table_name, conflict_columns) in SHEET_CONFIG.items():
        df = pd.read_excel(EXCEL_PATH, sheet_name=sheet_name).dropna(how="all")

        # Normalize dates
        for col in DATE_COLUMNS.get(sheet_name, []):
            df[col] = pd.to_datetime(df[col], errors="raise").dt.strftime("%Y-%m-%d")

        # Force integers
        for col in INT_COLUMNS.get(sheet_name, []):
            df[col] = pd.to_numeric(df[col], errors="raise").astype(int)

        records = dataframe_records(df)
        print(f"   {sheet_name} → {table_name}: {len(records)} rows")

        for chunk in batched(records, 100):
            supabase.table(table_name).upsert(
                chunk, on_conflict=conflict_columns
            ).execute()

    print("\n✅ Excel import complete!")


if __name__ == "__main__":
    load_excel_to_supabase()
