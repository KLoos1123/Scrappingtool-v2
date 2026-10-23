-- Ranglijst voor de easter eggs Flappy Mat en Snake: één rij per gebruiker met
-- de beste scores, credits en gekochte personages. Eenmalig uitvoeren in de Supabase SQL
-- Editor.
--
-- Lezen: alle ingelogde, niet-geblokkeerde gebruikers (voor de ranglijst).
-- Schrijven: alleen je eigen rij.

create table if not exists public.flappy_scores (
    user_id        uuid primary key references auth.users(id) on delete cascade,
    naam           text not null,
    beste          integer not null default 0 check (beste between 0 and 100000),
    credits        integer not null default 0 check (credits between 0 and 10000000),
    gekocht        text[] not null default array['mat'],
    keuze          text not null default 'mat',
    gespeeld       integer not null default 0,
    snake_beste    integer not null default 0 check (snake_beste between 0 and 100000),
    bijgewerkt_op  timestamptz not null default now()
);

-- Voor wie dit bestand al eerder heeft uitgevoerd: Snake-score erbij.
alter table public.flappy_scores add column if not exists snake_beste integer not null default 0;

alter table public.flappy_scores enable row level security;

drop policy if exists "flappy lezen" on public.flappy_scores;
create policy "flappy lezen" on public.flappy_scores
    for select to authenticated
    using (exists (
        select 1 from public.profiles p
        where p.id = auth.uid() and coalesce(p.status, '') <> 'blocked'
    ));

drop policy if exists "flappy eigen rij toevoegen" on public.flappy_scores;
create policy "flappy eigen rij toevoegen" on public.flappy_scores
    for insert to authenticated
    with check (user_id = auth.uid());

drop policy if exists "flappy eigen rij wijzigen" on public.flappy_scores;
create policy "flappy eigen rij wijzigen" on public.flappy_scores
    for update to authenticated
    using (user_id = auth.uid())
    with check (user_id = auth.uid());
