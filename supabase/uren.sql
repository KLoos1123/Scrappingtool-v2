-- Uren per week, kenmerken (contractvorm, startdatum, duur, verlenging) en
-- dubbels (groep, ook_op: dezelfde opdracht bij andere bronnen, zie dubbels.py)
-- naast het tarief (zie tarieven.py). Eenmalig uitvoeren in de Supabase SQL Editor, na
-- notities_tarieven.sql; opnieuw uitvoeren kan geen kwaad. Tot dan synct de
-- scraper alleen de tarieven.

alter table public.tarieven alter column tarief drop not null;
alter table public.tarieven add column if not exists uren      text;
alter table public.tarieven add column if not exists uren_min  numeric;
alter table public.tarieven add column if not exists uren_max  numeric;
alter table public.tarieven add column if not exists contractvorm text;
alter table public.tarieven add column if not exists startdatum   text;
alter table public.tarieven add column if not exists duur         text;
alter table public.tarieven add column if not exists verlenging   text;
alter table public.tarieven add column if not exists groep        text;
alter table public.tarieven add column if not exists ook_op       text;
