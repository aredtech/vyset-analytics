# Event Retention API Quick Reference

## Overview
This document provides a quick reference for the Event Retention API endpoints.

## Base URL
```
http://localhost:8069/api
```

## Endpoints

### 1. Get Retention Statistics
```http
GET /retention/stats
```

**Description**: Get retention statistics for all cameras

**Response Example**:
```json
{
    "message": "Retention statistics retrieved successfully",
    "stats": {
        "camera_001": {
            "retention_days": 30,
            "total_events": 1500,
            "events_within_retention": 1200,
            "events_outside_retention": 300,
            "oldest_event": "2024-01-01T00:00:00",
            "newest_event": "2024-01-31T23:59:59",
            "cutoff_date": "2024-01-01T00:00:00"
        }
    },
    "total_cameras": 1
}
```

### 2. Manual Cleanup (All Cameras)
```http
POST /retention/cleanup
```

**Description**: Trigger retention cleanup for all cameras

**Response Example**:
```json
{
    "message": "Manual cleanup completed",
    "results": {
        "camera_001": {
            "deleted_events": 300,
            "deleted_snapshots": 250,
            "retention_days": 30
        }
    },
    "summary": {
        "total_deleted_events": 300,
        "total_deleted_snapshots": 250,
        "cameras_processed": 1
    }
}
```

### 3. Manual Cleanup (Specific Camera)
```http
POST /retention/cleanup/{camera_id}
```

**Description**: Trigger retention cleanup for a specific camera

**Parameters**:
- `camera_id` (path): Camera identifier

**Response Example**:
```json
{
    "message": "Cleanup completed for camera camera_001",
    "camera_id": "camera_001",
    "retention_days": 30,
    "deleted_events": 150,
    "deleted_snapshots": 120
}
```

### 4. Get Scheduler Status
```http
GET /retention/scheduler/status
```

**Description**: Get retention scheduler status information

**Response Example**:
```json
{
    "message": "Scheduler status retrieved successfully",
    "scheduler": {
        "running": true,
        "cleanup_interval_hours": 24,
        "last_cleanup": "2024-01-31T02:00:00",
        "next_cleanup": "2024-02-01T02:00:00",
        "thread_alive": true
    }
}
```

### 5. Start Scheduler
```http
POST /retention/scheduler/start
```

**Description**: Start the retention scheduler

**Response Example**:
```json
{
    "message": "Retention scheduler started successfully",
    "status": "started"
}
```

### 6. Stop Scheduler
```http
POST /retention/scheduler/stop
```

**Description**: Stop the retention scheduler

**Response Example**:
```json
{
    "message": "Retention scheduler stopped successfully",
    "status": "stopped"
}
```

## cURL Examples

### Get Retention Statistics
```bash
curl -X GET http://localhost:8069/api/retention/stats
```

### Trigger Cleanup for All Cameras
```bash
curl -X POST http://localhost:8069/api/retention/cleanup
```

### Trigger Cleanup for Specific Camera
```bash
curl -X POST http://localhost:8069/api/retention/cleanup/camera_001
```

### Get Scheduler Status
```bash
curl -X GET http://localhost:8069/api/retention/scheduler/status
```

### Start Scheduler
```bash
curl -X POST http://localhost:8069/api/retention/scheduler/start
```

### Stop Scheduler
```bash
curl -X POST http://localhost:8069/api/retention/scheduler/stop
```

## Python Examples

### Get Retention Statistics
```python
import requests

response = requests.get("http://localhost:8069/api/retention/stats")
stats = response.json()
print(f"Total cameras: {stats['total_cameras']}")
```

### Trigger Manual Cleanup
```python
import requests

# Cleanup all cameras
response = requests.post("http://localhost:8069/api/retention/cleanup")
result = response.json()
print(f"Deleted {result['summary']['total_deleted_events']} events")

# Cleanup specific camera
response = requests.post("http://localhost:8069/api/retention/cleanup/camera_001")
result = response.json()
print(f"Deleted {result['deleted_events']} events for camera_001")
```

### Monitor Scheduler
```python
import requests

response = requests.get("http://localhost:8069/api/retention/scheduler/status")
status = response.json()
scheduler = status['scheduler']

print(f"Scheduler running: {scheduler['running']}")
print(f"Last cleanup: {scheduler['last_cleanup']}")
print(f"Next cleanup: {scheduler['next_cleanup']}")
```

## Error Responses

All endpoints return appropriate HTTP status codes:

- `200 OK`: Success
- `404 Not Found`: Camera not found (for camera-specific endpoints)
- `500 Internal Server Error`: Server error

Error response format:
```json
{
    "detail": "Error message describing what went wrong"
}
```

## Notes

- All endpoints return JSON responses
- All timestamps are in ISO format (UTC)
- The scheduler runs automatically every 24 hours
- Manual cleanup can be triggered at any time
- Cleanup operations are logged for monitoring
- Snapshot files are automatically deleted with their associated events
