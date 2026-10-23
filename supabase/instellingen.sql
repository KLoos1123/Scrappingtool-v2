-- Gedeelde instellingen van het dashboard, nu: de lijst met statussen (naam,
-- kleur, telt als "in behandeling"). Eenmalig uitvoeren in de Supabase SQL
-- Editor. Tot dan gebruikt het dashboard de standaardlijst uit marktlogica.js.
--
-- Lezen: alle ingelogde, niet-geblokkeerde gebruikers. Schrijven: alleen admins
-- (via de Beheer-pagina).

create table if not exists public.instellingen (
    sleutel         text primary key,
    waarde          jsonb not null,
    gewijzigd_door  text,
    gewijzigd_op    timestamptz not null default now()
);

alter table public.instellingen enable row level security;

drop policy if exists "instellingen lezen" on public.instellingen;
create policy "instellingen lezen" on public.instellingen
    for select to authenticated
    using (exists (
        select 1 from public.profiles p
        where p.id = auth.uid() and coalesce(p.status, '') <> 'blocked'
    ));

drop policy if exists "instellingen toevoegen door admin" on public.instellingen;
create policy "instellingen toevoegen door admin" on public.instellingen
    for insert to authenticated
    with check (exists (
        select 1 from public.profiles p
        where p.id = auth.uid() and p.role = 'admin' and coalesce(p.status, '') <> 'blocked'
    ));

drop policy if exists "instellingen wijzigen door admin" on public.instellingen;
create policy "instellingen wijzigen door admin" on public.instellingen
    for update to authenticated
    using (exists (
        select 1 from public.profiles p
        where p.id = auth.uid() and p.role = 'admin' and coalesce(p.status, '') <> 'blocked'
    ))
    with check (exists (
        select 1 from public.profiles p
        where p.id = auth.uid() and p.role = 'admin' and coalesce(p.status, '') <> 'blocked'
    ));
