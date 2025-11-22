-- Migration script to add camera_name column to events table
-- Run this script to update existing database schema

-- Add camera_name column to events table
ALTER TABLE events ADD COLUMN IF NOT EXISTS camera_name VARCHAR(255);

-- Optional: Update existing records with a default camera name based on camera_id
-- Uncomment the line below if you want to populate existing records
-- UPDATE events SET camera_name = 'Camera ' || camera_id WHERE camera_name IS NULL;

-- Verify the change
SELECT column_name, data_type, is_nullable 
FROM information_schema.columns 
WHERE table_name = 'events' AND column_name = 'camera_name';

