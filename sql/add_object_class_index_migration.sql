-- Migration to add index for object_class filtering
-- This adds an index on the class_name field within the event_data JSON column

-- For PostgreSQL (most common)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_event_data_class_name 
ON events USING btree ((event_data->>'class_name'));

-- Alternative for MySQL (if using MySQL)
-- CREATE INDEX idx_event_data_class_name ON events ((JSON_UNQUOTE(JSON_EXTRACT(event_data, '$.class_name'))));

-- Alternative for SQLite (if using SQLite)
-- CREATE INDEX idx_event_data_class_name ON events (json_extract(event_data, '$.class_name'));

-- Note: The CONCURRENTLY option allows the index to be created without blocking reads/writes
-- Remove CONCURRENTLY if your PostgreSQL version doesn't support it or if you're using MySQL/SQLite
