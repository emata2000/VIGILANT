-- Se ejecuta una sola vez, al crear el volumen de Postgres.
-- La app usa un rol SIN superusuario: los superusuarios se saltan Row-Level Security.
CREATE ROLE vigilant LOGIN PASSWORD 'vigilant';
CREATE DATABASE vigilant OWNER vigilant;
\c vigilant
CREATE EXTENSION IF NOT EXISTS postgis;
