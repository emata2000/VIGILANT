-- Preparar la base de Supabase (o Neon) para VIGILANT.
-- Ejecutar UNA vez en el editor SQL del proyecto, cambiando la contraseña.
--
-- Por qué un rol propio: el rol "postgres" de Supabase se salta Row-Level Security,
-- y RLS es lo que impide que una empresa vea los datos de otra.

CREATE ROLE vigilant_app LOGIN PASSWORD 'CAMBIA-ESTA-CONTRASEÑA' NOBYPASSRLS;

-- PostGIS (en Supabase va en el esquema "extensions").
CREATE EXTENSION IF NOT EXISTS postgis WITH SCHEMA extensions;

-- La app crea sus tablas en "public" y usa las funciones de PostGIS de "extensions".
GRANT USAGE, CREATE ON SCHEMA public TO vigilant_app;
GRANT USAGE ON SCHEMA extensions TO vigilant_app;
ALTER ROLE vigilant_app SET search_path = public, extensions;

-- Comprobación: debe decir false en ambas columnas.
SELECT rolsuper, rolbypassrls FROM pg_roles WHERE rolname = 'vigilant_app';
