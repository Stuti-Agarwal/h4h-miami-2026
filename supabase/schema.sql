-- Run once in the Supabase SQL editor (or via scripts/load_supabase.py).
create extension if not exists postgis;

create table if not exists buildings (
  id bigserial primary key,
  geom geometry(Geometry, 4326) not null,
  height real,
  num_floors int
);
create table if not exists places (
  id bigserial primary key,
  geom geometry(Point, 4326) not null,
  name text,
  category text,
  confidence real
);
create table if not exists lights (
  id bigserial primary key,
  geom geometry(Point, 4326) not null
);
create table if not exists stops (
  id bigserial primary key,
  geom geometry(Point, 4326) not null
);
create table if not exists osm_lit (  -- OSM street lamps (points) and lit=yes streets (lines)
  id bigserial primary key,
  geom geometry(Geometry, 4326) not null
);
create table if not exists highways (  -- OSM elevated motorway/trunk bridges (lines)
  id bigserial primary key,
  geom geometry(Geometry, 4326) not null
);
create table if not exists incidents (  -- City of Miami PD reported crimes, geocoded to block
  id bigserial primary key,
  geom geometry(Point, 4326) not null,
  category text,
  date text
);
create table if not exists traffic (  -- FDOT Annual Average Daily Traffic segments (lines), expressways excluded
  id bigserial primary key,
  geom geometry(Geometry, 4326) not null,
  aadt int,
  road text
);
create table if not exists routes (
  name text primary key,
  distance_m int not null,
  geom geometry(LineString, 4326) not null
);

create index if not exists buildings_geom on buildings using gist (geom);
create index if not exists places_geom on places using gist (geom);
create index if not exists lights_geom on lights using gist (geom);
create index if not exists stops_geom on stops using gist (geom);
create index if not exists osm_lit_geom on osm_lit using gist (geom);
create index if not exists highways_geom on highways using gist (geom);
create index if not exists incidents_geom on incidents using gist (geom);
create index if not exists traffic_geom on traffic using gist (geom);
