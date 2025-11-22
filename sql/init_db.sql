-- Database initialization script
-- This script creates the analytics database if it doesn't exist

-- Create the analytics database (if not exists)
-- Note: This will be executed when the postgres container is first initialized
SELECT 'CREATE DATABASE vms_analytics_db'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'vms_analytics_db')\gexec

-- Grant permissions
GRANT ALL PRIVILEGES ON DATABASE vms_analytics_db TO vms_admin;

\c vms_analytics_db

-- The tables will be created by SQLAlchemy when the app starts
-- This file is just to ensure the database exists

