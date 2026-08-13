-- Grade Pending NYC — raw inspection data
--
-- One row = one violation cited on one inspection (matching the source NYC
-- DOHMH feed's own grain — see ../NOTES.md). Not one restaurant, not one
-- inspection visit. Every Python analysis script in this repo groups by
-- (camis, inspection_date) or (camis, inspection_date, inspection_type)
-- before computing anything; querying this table directly without that
-- grouping will double-count restaurants with multiple citations on the
-- same visit, exactly like the raw JSON extract does.
--
-- This is groundwork for a possible future live version of the site (see
-- the "Supabase" section in README.md) — nothing in the current static
-- site or analysis scripts reads from this table yet, and it isn't
-- deployed anywhere. Run this once in the Supabase SQL editor after
-- creating a project, then see load_data.py to populate it.

create table if not exists inspections (
    id bigint generated always as identity primary key,
    camis text not null,
    dba text,
    boro text,
    building text,
    street text,
    zipcode text,
    phone text,
    cuisine_description text,
    inspection_date timestamptz,
    inspection_type text,
    action text,
    violation_code text,
    violation_description text,
    critical_flag text,
    score integer,
    grade text,
    grade_date timestamptz,
    record_date timestamptz,
    latitude double precision,
    longitude double precision,
    community_board text,
    council_district text,
    census_tract text,
    bin text,
    bbl text,
    nta text
);

comment on table inspections is
    'Raw NYC DOHMH restaurant inspection rows, one per violation cited on one inspection. See ../NOTES.md.';

-- Matches the fields the analysis scripts actually filter/group on
-- (regression.py's build_paired_dataset, investigate_borough_gap.py).
create index if not exists inspections_camis_idx on inspections (camis);
create index if not exists inspections_boro_idx on inspections (boro);
create index if not exists inspections_inspection_date_idx on inspections (inspection_date);
create index if not exists inspections_inspection_type_idx on inspections (inspection_type);
