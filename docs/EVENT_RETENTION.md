# Event Retention Feature

## Overview

The Event Retention feature provides automatic cleanup of events and snapshots based on configurable retention policies per camera. This helps manage storage space and ensures compliance with data retention requirements.

## Features

- **Per-Camera Retention**: Each camera can have its own retention period (1-365 days)
- **Automatic Cleanup**: Scheduled background task runs every 24 hours
- **Manual Cleanup**: API endpoints for manual cleanup triggers
- **Snapshot Management**: Automatically deletes associated snapshot files
- **Statistics & Monitoring**: API endpoints for monitoring retention status

## Configuration

### Camera Parameters

Each camera configuration now includes a `retention_days` parameter:

```python
{
    "camera_id": "camera_001",
    "camera_name": "Main Entrance",
    "stream_url": "rtsp://camera.example.com/stream",
    "parameters": {
        "retention_days": 30,  # Keep events for 30 days
        "enable_object_detection": true,
        "enable_motion_detection": true,
        # ... other parameters
    }
}
```

**Retention Days Range**: 1-365 days (default: 30 days)

## API Endpoints

### 1. Get Retention Statistics

```http
GET /api/retention/stats
```

**Response:**
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
POST /api/retention/cleanup
```

**Response:**
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
POST /api/retention/cleanup/{camera_id}
```

**Response:**
```json
{
    "message": "Cleanup completed for camera camera_001",
    "camera_id": "camera_001",
    "retention_days": 30,
    "deleted_events": 150,
    "deleted_snapshots": 120
}
```

### 4. Scheduler Status

```http
GET /api/retention/scheduler/status
```

**Response:**
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

### 5. Start/Stop Scheduler

```http
POST /api/retention/scheduler/start
POST /api/retention/scheduler/stop
```

## Implementation Details

### Components

1. **RetentionService** (`app/services/retention.py`)
   - Core logic for event cleanup
   - Handles database operations
   - Manages snapshot file deletion
   - Provides statistics and monitoring

2. **RetentionScheduler** (`app/services/retention_scheduler.py`)
   - Background task scheduler
   - Runs cleanup every 24 hours
   - Provides manual trigger capabilities
   - Status monitoring

3. **Enhanced SnapshotManager** (`app/utils/snapshot.py`)
   - Added `delete_snapshot()` method
   - Supports snapshot file deletion

4. **API Endpoints** (`app/api/cameras.py`)
   - RESTful endpoints for retention management
   - Manual cleanup triggers
   - Statistics and monitoring

### Database Schema

Events are stored in the `events` table with the following relevant fields:

```sql
CREATE TABLE events (
    id SERIAL PRIMARY KEY,
    event_type VARCHAR(50) NOT NULL,
    camera_id VARCHAR(100) NOT NULL,
    timestamp TIMESTAMP NOT NULL,
    snapshot_path VARCHAR(500),
    event_data JSONB NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- Indexes for efficient cleanup queries
CREATE INDEX idx_camera_timestamp ON events(camera_id, timestamp);
CREATE INDEX idx_event_type_timestamp ON events(event_type, timestamp);
```

### Cleanup Process

1. **Event Identification**: Query events older than retention period
2. **Snapshot Cleanup**: Delete associated snapshot files
3. **Database Cleanup**: Remove event records from database
4. **Logging**: Comprehensive logging of cleanup operations

### Scheduler Behavior

- **Startup**: Automatically starts when the application launches
- **Interval**: Runs every 24 hours (configurable)
- **Graceful Shutdown**: Stops cleanly when application shuts down
- **Error Handling**: Continues running even if individual cleanup operations fail
- **Monitoring**: Provides status information via API

## Usage Examples

### Setting Up Camera with Retention

```python
from app.models.event_models import CameraConfig, CameraParameters

# Create camera with 7-day retention
camera_config = CameraConfig(
    camera_id="entrance_cam",
    camera_name="Main Entrance",
    stream_url="rtsp://192.168.1.100/stream",
    parameters=CameraParameters(
        retention_days=7,  # Keep events for 7 days
        enable_object_detection=True,
        enable_motion_detection=True
    )
)
```

### Manual Cleanup via API

```bash
# Trigger cleanup for all cameras
curl -X POST http://localhost:8069/api/retention/cleanup

# Trigger cleanup for specific camera
curl -X POST http://localhost:8069/api/retention/cleanup/entrance_cam

# Check retention statistics
curl http://localhost:8069/api/retention/stats

# Check scheduler status
curl http://localhost:8069/api/retention/scheduler/status
```

### Monitoring Retention

```python
import requests

# Get retention statistics
response = requests.get("http://localhost:8069/api/retention/stats")
stats = response.json()

for camera_id, camera_stats in stats["stats"].items():
    print(f"Camera {camera_id}:")
    print(f"  Retention: {camera_stats['retention_days']} days")
    print(f"  Total Events: {camera_stats['total_events']}")
    print(f"  Events to Delete: {camera_stats['events_outside_retention']}")
```

## Configuration Options

### Environment Variables

The retention feature uses existing configuration. No additional environment variables are required.

### Scheduler Configuration

The scheduler interval can be modified in `app/services/retention_scheduler.py`:

```python
# Change from 24 hours to 12 hours
retention_scheduler = RetentionScheduler(cleanup_interval_hours=12)
```

## Best Practices

1. **Retention Periods**: Set appropriate retention periods based on:
   - Legal/compliance requirements
   - Storage capacity
   - Business needs

2. **Monitoring**: Regularly check retention statistics to ensure proper operation

3. **Manual Cleanup**: Use manual cleanup for immediate space recovery

4. **Backup Considerations**: Ensure important events are backed up before retention periods expire

5. **Storage Management**: Monitor snapshot directory size and adjust retention periods as needed

## Troubleshooting

### Common Issues

1. **Scheduler Not Running**
   - Check application logs for startup errors
   - Verify scheduler status via API
   - Restart scheduler if needed

2. **Cleanup Not Working**
   - Check database connectivity
   - Verify camera configurations
   - Review error logs

3. **Snapshot Files Not Deleted**
   - Check file permissions
   - Verify snapshot directory exists
   - Run orphaned cleanup manually

### Logging

All retention operations are logged with appropriate levels:
- **INFO**: Normal operations, cleanup summaries
- **DEBUG**: Detailed operation information
- **ERROR**: Failures and exceptions
- **WARNING**: Non-critical issues

## Migration Notes

### Existing Cameras

Existing cameras will use the default retention period of 30 days. Update camera configurations to set specific retention periods as needed.

### Database Impact

The retention feature uses existing database indexes and doesn't require schema changes. Cleanup operations are optimized for performance.

### Performance Considerations

- Cleanup operations run during low-activity periods
- Database queries are optimized with proper indexes
- File operations are batched for efficiency
- Scheduler runs in background thread to avoid blocking
