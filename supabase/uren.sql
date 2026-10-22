-- Uren per week naast het tarief (zie tarieven.py). Eenmalig uitvoeren in de
-- Supabase SQL Editor, na notities_tarieven.sql. Tot dan synct de scraper
-- alleen de tarieven, zonder uren.

alter table public.tarieven alter column tarief drop not null;
alter table public.tarieven add column if not exists uren      text;
alter table public.tarieven add column if not exists uren_min  numeric;
alter table public.tarieven add column if not exists uren_max  numeric;
