# Camera Name Feature

## Overview
Added support for human-readable camera names that are included in camera registration responses and all event records.

## Changes Made

### 1. Data Models (`app/models/event_models.py`)
- Added `camera_name` field to `CameraConfig` model
  ```python
  camera_name: Optional[str] = Field(default=None, description="Human-readable camera name")
  ```

### 2. Database Schema (`app/models/db_models.py`)
- Added `camera_name` column to `EventRecord` table
  ```python
  camera_name = Column(String(255), nullable=True)
  ```

### 3. Camera Registration API (`app/api/cameras.py`)
- Updated registration response to include `camera_name` in success/failed results
- Now returns:
  ```json
  {
    "message": "Processed X camera(s)",
    "results": {
      "success": [
        {
          "camera_id": "cam_001",
          "camera_name": "Front Entrance"
        }
      ],
      "failed": []
    }
  }
  ```

### 4. Events API (`app/api/events.py`)
- Added `camera_name` to `EventResponse` model
- All event queries now return `camera_name` along with `camera_id`

### 5. Event Processing (`app/services/video_worker.py`)
- Updated `save_and_publish_event` function to accept and store `camera_name`
- All event types (detection, motion, anpr, tracking) now include `camera_name`
- Redis Pub/Sub messages now include `camera_name`

## Usage

### Registering a Camera with Name
```json
POST /api/cameras
{
  "cameras": [
    {
      "camera_id": "cam_001",
      "camera_name": "Front Entrance",
      "stream_url": "rtsp://...",
      "parameters": {
        ...
      }
    }
  ]
}
```

### Response Example
```json
{
  "message": "Processed 1 camera(s)",
  "results": {
    "success": [
      {
        "camera_id": "cam_001",
        "camera_name": "Front Entrance"
      }
    ],
    "failed": []
  }
}
```

### Event Response Example
```json
{
  "id": 123,
  "event_type": "detection",
  "camera_id": "cam_001",
  "camera_name": "Front Entrance",
  "timestamp": "2025-10-11T10:30:00Z",
  "frame_number": 100,
  "snapshot_path": "snapshots/...",
  "event_data": {...},
  "created_at": "2025-10-11T10:30:01Z"
}
```

### Redis Pub/Sub Event Format
Published events now include `camera_name`:
```json
{
  "id": 123,
  "event_type": "detection",
  "camera_id": "cam_001",
  "camera_name": "Front Entrance",
  "timestamp": "2025-10-11T10:30:00Z",
  "frame_number": 100,
  "snapshot_path": "snapshots/...",
  "event_data": {...},
  "created_at": "2025-10-11T10:30:01Z"
}
```

## Database Migration

If you have an existing database, run the migration script:
```bash
psql -U your_user -d your_database -f add_camera_name_migration.sql
```

Or using Docker:
```bash
docker exec -i postgres_container psql -U your_user -d your_database < add_camera_name_migration.sql
```

## Notes
- `camera_name` is optional; if not provided, it will be `null`
- Existing events without `camera_name` will have `null` value
- The field is nullable to maintain backward compatibility
- Camera name is logged in all event processing messages for better traceability

