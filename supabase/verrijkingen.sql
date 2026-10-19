-- AI-verrijking per tender (zie verrijking.py). Eenmalig uitvoeren in de
-- Supabase SQL Editor. Schrijven gebeurt alleen door de scraper met de
-- service_role key; ingelogde, niet-geblokkeerde gebruikers mogen lezen.

create table if not exists public.verrijkingen (
    bron                text not null,
    tender_id           text not null,
    eindklant           text,
    eindklant_zekerheid text,
    senioriteit         text,
    modules             jsonb not null default '[]'::jsonb,
    data                jsonb not null,
    model               text,
    verrijkt_op         timestamptz not null,
    primary key (bron, tender_id)
);

alter table public.verrijkingen enable row level security;

drop policy if exists "verrijkingen lezen" on public.verrijkingen;
create policy "verrijkingen lezen" on public.verrijkingen
    for select to authenticated
    using (exists (
        select 1 from public.profiles p
        where p.id = auth.uid() and coalesce(p.status, '') <> 'blocked'
    ));
