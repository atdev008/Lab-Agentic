-- ============================================================
-- Agentic AI + Supabase Training Lab
-- Run this ONCE in Supabase -> SQL Editor
-- ============================================================

create extension if not exists vector
with schema extensions;

-- --------------------------
-- Structured business tables
-- --------------------------

create table if not exists customers (
    customer_code text primary key,
    customer_name text not null,
    customer_type text,
    province text,
    credit_term_days integer,
    credit_limit_thb numeric(14,2),
    risk_level text,
    status text
);

create table if not exists products (
    sku text primary key,
    product_name text not null,
    category text,
    unit_price_thb numeric(14,2),
    minimum_stock integer,
    cost_thb numeric(14,2)
);

create table if not exists inventory (
    sku text not null references products(sku) on update cascade,
    warehouse text not null,
    quantity_on_hand integer,
    minimum_stock integer,
    stock_status text,
    primary key (sku, warehouse)
);

create table if not exists invoices (
    invoice_no text primary key,
    customer_code text references customers(customer_code) on update cascade,
    customer_name text,
    invoice_date date,
    due_date date,
    amount_thb numeric(14,2),
    paid_amount_thb numeric(14,2),
    outstanding_thb numeric(14,2),
    status text,
    overdue_days integer
);

create table if not exists payments (
    payment_no text primary key,
    invoice_no text references invoices(invoice_no) on update cascade,
    customer_code text references customers(customer_code) on update cascade,
    payment_date date,
    amount_thb numeric(14,2),
    payment_method text
);

create table if not exists employees (
    employee_code text primary key,
    employee_name text not null,
    department text,
    position text,
    salary_thb numeric(14,2),
    start_date date,
    status text
);

-- --------------------------
-- RAG / pgvector table
-- text-embedding-3-small defaults to 1536 dimensions.
-- If you change embedding model/dimensions, change vector(1536) too.
-- --------------------------

create table if not exists knowledge_documents (
    id bigint generated always as identity primary key,
    title text,
    source_file text not null,
    storage_path text,
    chunk_index integer not null,
    content text not null,
    metadata jsonb default '{}'::jsonb,
    embedding extensions.vector(1536),
    created_at timestamptz default now(),
    unique (source_file, chunk_index)
);

-- --------------------------
-- Similarity search RPC
-- --------------------------

create or replace function match_documents (
    query_embedding extensions.vector(1536),
    match_threshold double precision default 0.30,
    match_count integer default 5
)
returns table (
    id bigint,
    title text,
    source_file text,
    chunk_index integer,
    content text,
    metadata jsonb,
    similarity double precision
)
language sql
stable
as $$
    select
        kd.id,
        kd.title,
        kd.source_file,
        kd.chunk_index,
        kd.content,
        kd.metadata,
        1 - (kd.embedding <=> query_embedding) as similarity
    from knowledge_documents kd
    where kd.embedding is not null
      and 1 - (kd.embedding <=> query_embedding) >= match_threshold
    order by kd.embedding <=> query_embedding
    limit match_count;
$$;

-- Optional: vector index. For a tiny teaching dataset this is not necessary.
-- It becomes useful when the number of chunks grows.
--
-- create index if not exists knowledge_documents_embedding_hnsw_idx
-- on knowledge_documents
-- using hnsw (embedding vector_cosine_ops);

-- --------------------------
-- Useful test SQL
-- --------------------------

-- Products below minimum:
-- select * from inventory where quantity_on_hand < minimum_stock;

-- Overdue invoices:
-- select *
-- from invoices
-- where outstanding_thb > 0
-- order by overdue_days desc;
