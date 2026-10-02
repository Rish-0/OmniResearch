-- Create the mlflow database for MLflow tracking server
CREATE DATABASE mlflow;

-- Create extensions in the main database
\c omniresearch;
CREATE EXTENSION IF NOT EXISTS "pgcrypto";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";
