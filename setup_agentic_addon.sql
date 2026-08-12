-- ============================================================
-- Agentic AI Lab Add-on
-- Run after setup_supabase.sql
-- ============================================================

create table if not exists agent_actions (
    id bigint generated always as identity primary key,
    action_type text not null,
    customer_code text,
    customer_name text,
    reason text,
    evidence jsonb default '{}'::jsonb,
    status text not null default 'DRAFT'
        check (status in ('DRAFT','APPROVED','REJECTED','EXECUTED')),
    created_at timestamptz default now(),
    reviewed_at timestamptz,
    reviewed_by text
);

create index if not exists agent_actions_status_idx
on agent_actions(status);

-- Optional run log table for later observability
create table if not exists agent_run_logs (
    id bigint generated always as identity primary key,
    question text not null,
    final_answer text,
    tools_used jsonb default '[]'::jsonb,
    created_at timestamptz default now()
);
