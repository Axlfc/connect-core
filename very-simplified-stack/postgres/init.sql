-- Enable pgvector in the default database
CREATE EXTENSION IF NOT EXISTS vector;

-- Create forgejo database
SELECT 'CREATE DATABASE forgejo' WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'forgejo')\gexec
