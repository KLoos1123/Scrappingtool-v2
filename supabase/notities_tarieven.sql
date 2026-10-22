-- Notities per opdracht (geschikt voor, tarief, opmerking) en gescrapete
-- tarieven. Eenmalig uitvoeren in de Supabase SQL Editor.
--
-- notities: ingelogde, niet-geblokkeerde gebruikers mogen lezen en schrijven
--           (vanuit het dashboard en de bronnenpagina).
-- tarieven: alleen de scraper schrijft (service_role, zie tarieven.py en
--           supabase_sync.sync_tarieven); gebruikers mogen lezen.

create table if not exists public.notities (
    bron            text not null,
    tender_id       text not null,
    geschikt_voor   text,
    tarief          text,
    opmerking       text,
    gewijzigd_door  text,
    gewijzigd_op    timestamptz not null default now(),
    primary key (bron, tender_id)
);

alter table public.notities enable row level security;

drop policy if exists "notities lezen" on public.notities;
create policy "notities lezen" on public.notities
    for select to authenticated
    using (exists (
        select 1 from public.profiles p
        where p.id = auth.uid() and coalesce(p.status, '') <> 'blocked'
    ));

drop policy if exists "notities toevoegen" on public.notities;
create policy "notities toevoegen" on public.notities
    for insert to authenticated
    with check (exists (
        select 1 from public.profiles p
        where p.id = auth.uid() and coalesce(p.status, '') <> 'blocked'
    ));

drop policy if exists "notities wijzigen" on public.notities;
create policy "notities wijzigen" on public.notities
    for update to authenticated
    using (exists (
        select 1 from public.profiles p
        where p.id = auth.uid() and coalesce(p.status, '') <> 'blocked'
    ));

-- live bijwerken bij collega's die het dashboard open hebben
do $$ begin
    alter publication supabase_realtime add table public.notities;
exception when duplicate_object then null;
end $$;


create table if not exists public.tarieven (
    bron         text not null,
    tender_id    text not null,
    tarief       text not null,
    tarief_min   numeric,
    tarief_max   numeric,
    herkomst     text,
    gevonden_op  timestamptz not null,
    primary key (bron, tender_id)
);

alter table public.tarieven enable row level security;

drop policy if exists "tarieven lezen" on public.tarieven;
create policy "tarieven lezen" on public.tarieven
    for select to authenticated
    using (exists (
        select 1 from public.profiles p
        where p.id = auth.uid() and coalesce(p.status, '') <> 'blocked'
    ));
