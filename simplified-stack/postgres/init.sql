-- Enable pgvector in the default database
CREATE EXTENSION IF NOT EXISTS vector;

-- Create drupal database
SELECT 'CREATE DATABASE drupal' WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'drupal')\gexec

-- Create forgejo database
SELECT 'CREATE DATABASE forgejo' WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'forgejo')\gexec
