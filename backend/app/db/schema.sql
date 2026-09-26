-- Yatra AI — Supabase schema
-- Run in the Supabase SQL editor. Creates profile, preference, trip and
-- OTP tables with Row Level Security so users can only reach their own
-- private data. email_otps / pending_registrations have NO public
-- policies: they are service-role only (OTP verification runs server-side).

-- ── public.users ────────────────────────────────────────────────────────
create table if not exists public.users (
  id          uuid primary key references auth.users(id) on delete cascade,
  email       text not null unique,
  username    text not null unique,
  full_name   text not null default '',
  created_at  timestamptz not null default now(),
  updated_at  timestamptz not null default now()
);

alter table public.users enable row level security;

create policy "users read own row"
  on public.users for select
  using (auth.uid() = id);

create policy "users update own row"
  on public.users for update
  using (auth.uid() = id)
  with check (auth.uid() = id);

-- ── public.travel_profiles ──────────────────────────────────────────────
create table if not exists public.travel_profiles (
  user_id                     uuid primary key references public.users(id) on delete cascade,
  preferred_budget            numeric,
  preferred_trip_style        text,
  food_preferences            text,
  accommodation_preferences   text,
  transportation_preferences  text,
  interests                   text[] default '{}',
  preferred_pace              text,
  created_at                  timestamptz not null default now(),
  updated_at                  timestamptz not null default now()
);

alter table public.travel_profiles enable row level security;

create policy "profiles read own"
  on public.travel_profiles for select
  using (auth.uid() = user_id);

create policy "profiles update own"
  on public.travel_profiles for update
  using (auth.uid() = user_id)
  with check (auth.uid() = user_id);

create policy "profiles insert own"
  on public.travel_profiles for insert
  with check (auth.uid() = user_id);

-- ── public.saved_trips ──────────────────────────────────────────────────
create table if not exists public.saved_trips (
  id          uuid primary key default gen_random_uuid(),
  user_id     uuid not null references public.users(id) on delete cascade,
  trip_name   text not null,
  origin      text,
  destination text,
  start_date  date,
  end_date    date,
  travelers   int,
  budget      numeric,
  itinerary   text,
  thread_id   text,           -- agent conversation thread for re-planning
  created_at  timestamptz not null default now(),
  updated_at  timestamptz not null default now()
);

create index if not exists saved_trips_user_idx
  on public.saved_trips (user_id);

alter table public.saved_trips enable row level security;

create policy "trips read own"
  on public.saved_trips for select
  using (auth.uid() = user_id);

create policy "trips insert own"
  on public.saved_trips for insert
  with check (auth.uid() = user_id);

create policy "trips update own"
  on public.saved_trips for update
  using (auth.uid() = user_id)
  with check (auth.uid() = user_id);

create policy "trips delete own"
  on public.saved_trips for delete
  using (auth.uid() = user_id);

-- ── auth plumbing tables (service-role only — no public policies) ───────
create table if not exists public.email_otps (
  id          uuid primary key default gen_random_uuid(),
  email       text not null,
  purpose     text not null check (purpose in ('verify','reset')),
  otp_hash    text not null,
  salt        text not null,
  attempts    int not null default 0,
  expires_at  timestamptz not null,
  created_at  timestamptz not null default now()
);

create index if not exists email_otps_lookup_idx
  on public.email_otps (email, purpose, created_at desc);

alter table public.email_otps enable row level security;
-- intentionally no policies: inaccessible to anon/authenticated roles

create table if not exists public.pending_registrations (
  email       text primary key,
  full_name   text not null default '',
  username    text not null default '',
  created_at  timestamptz not null default now()
);

alter table public.pending_registrations enable row level security;
-- intentionally no policies: service-role only
