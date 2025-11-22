# Snapshot Feature Documentation

## Overview

The Analytics Service now includes a comprehensive snapshot feature that automatically captures and stores images when events occur (motion, object detection/tracking, ANPR). Each snapshot is saved with bounding boxes drawn using Ultralytics visualization, and event metadata is stored in a PostgreSQL database.

## Features

### 1. **Automatic Snapshot Capture**
- **Motion Events**: Captures frame with motion areas highlighted in red overlay
- **Detection/Tracking Events**: Captures frame with bounding boxes and labels (class name, confidence, track ID)
- **ANPR Events**: Captures frame with license plate highlighted in green box and plate text displayed

### 2. **Database Storage**
- All events are stored in PostgreSQL database
- Event metadata includes: type, camera ID, timestamp, frame number, and event-specific data
- Efficient indexing for fast queries by camera, event type, and timestamp
- Snapshot file paths stored with events for easy retrieval

### 3. **RESTful API**
- List events with filtering and pagination
- Get event statistics
- Retrieve individual events
- Download snapshot images
- Delete events (with optional snapshot cleanup)

## Architecture

```
┌─────────────────┐
│  Video Stream   │
└────────┬────────┘
         │
         ▼
┌─────────────────────┐
│  Video Worker       │
│  - Frame Processing │
│  - Event Detection  │
└────────┬────────────┘
         │
         ├─────────────────┐
         │                 │
         ▼                 ▼
┌─────────────────┐ ┌──────────────────┐
│  Redis Stream   │ │  Database +      │
│  (Real-time)    │ │  Snapshots       │
│                 │ │  (Persistent)    │
└─────────────────┘ └──────────────────┘
                           │
                           ▼
                    ┌──────────────────┐
                    │   Events API     │
                    │  (REST Endpoints)│
                    └──────────────────┘
```

## Database Schema

### EventRecord Table

| Column | Type | Description |
|--------|------|-------------|
| id | Integer | Primary key (auto-increment) |
| event_type | String(50) | Event type: detection, motion, anpr, tracking |
| camera_id | String(100) | Camera identifier |
| timestamp | DateTime | Event timestamp (UTC) |
| frame_number | Integer | Frame number when event occurred |
| snapshot_path | String(500) | Relative path to snapshot image (nullable) |
| event_data | JSON | Event-specific data (detections, motion intensity, etc.) |
| created_at | DateTime | Record creation timestamp |

**Indexes:**
- `idx_camera_timestamp`: (camera_id, timestamp)
- `idx_event_type_timestamp`: (event_type, timestamp)

## API Endpoints

### 1. List Events
```http
GET /api/events
```

**Query Parameters:**
- `camera_id` (optional): Filter by camera ID
- `event_type` (optional): Filter by event type (detection, motion, anpr, tracking)
- `start_time` (optional): Start timestamp (ISO format)
- `end_time` (optional): End timestamp (ISO format)
- `page` (default: 1): Page number
- `page_size` (default: 50, max: 500): Items per page

**Response:**
```json
{
  "events": [
    {
      "id": 1,
      "event_type": "tracking",
      "camera_id": "camera-1",
      "timestamp": "2024-03-15T10:30:45.123456",
      "frame_number": 1234,
      "snapshot_path": "camera-1/2024-03-15/tracking_103045_123456.png",
      "event_data": {
        "track_id": 42,
        "tracking_action": "entered",
        "class_name": "person",
        "confidence": 0.95,
        "bounding_box": {...}
      },
      "created_at": "2024-03-15T10:30:45.123456"
    }
  ],
  "total": 150,
  "page": 1,
  "page_size": 50,
  "has_more": true
}
```

### 2. Get Event Statistics
```http
GET /api/events/stats
```

**Query Parameters:**
- `camera_id` (optional): Filter by camera ID
- `start_time` (optional): Start timestamp
- `end_time` (optional): End timestamp

**Response:**
```json
{
  "total_events": 1523,
  "events_by_type": {
    "detection": 456,
    "motion": 789,
    "anpr": 123,
    "tracking": 155
  },
  "events_by_camera": {
    "camera-1": 800,
    "camera-2": 723
  },
  "date_range": {
    "first_event": "2024-03-01T00:00:00",
    "last_event": "2024-03-15T23:59:59"
  }
}
```

### 3. Get Single Event
```http
GET /api/events/{event_id}
```

**Response:**
```json
{
  "id": 1,
  "event_type": "tracking",
  "camera_id": "camera-1",
  "timestamp": "2024-03-15T10:30:45.123456",
  "frame_number": 1234,
  "snapshot_path": "camera-1/2024-03-15/tracking_103045_123456.png",
  "event_data": {...},
  "created_at": "2024-03-15T10:30:45.123456"
}
```

### 4. Get Event Snapshot
```http
GET /api/events/{event_id}/snapshot
```

**Response:** PNG image file

**Headers:**
```
Content-Type: image/png
Content-Disposition: attachment; filename="event_{id}_snapshot.png"
```

### 5. Delete Event
```http
DELETE /api/events/{event_id}?delete_snapshot=false
```

**Query Parameters:**
- `delete_snapshot` (default: false): Also delete the snapshot file

**Response:**
```json
{
  "message": "Event 1 deleted successfully",
  "snapshot_deleted": false
}
```

## Snapshot Storage

### Directory Structure
```
/app/snapshots/
├── camera-1/
│   ├── 2024-03-15/
│   │   ├── motion_103045_123456.png
│   │   ├── tracking_103046_234567.png
│   │   └── anpr_103047_345678.png
│   └── 2024-03-16/
│       └── ...
└── camera-2/
    └── ...
```

### Naming Convention
- Format: `{event_type}_{HHMMSS}_{microseconds}.png`
- Example: `motion_143052_456789.png`
- Organized by camera ID and date (YYYY-MM-DD)

## Configuration

### Environment Variables

```bash
# Database configuration
DATABASE_URL=postgresql://vms_admin:AIvan0987@db:5432/vms_analytics_db

# Snapshot configuration
SNAPSHOTS_DIR=/app/snapshots
ENABLE_SNAPSHOTS=true
```

### Docker Volumes

```yaml
volumes:
  - analytics_snapshots:/app/snapshots  # Persistent storage
```

## Usage Examples

### Example 1: Get Recent Motion Events

```bash
curl "http://localhost:8069/api/events?event_type=motion&page=1&page_size=10"
```

### Example 2: Download Event Snapshot

```bash
curl "http://localhost:8069/api/events/123/snapshot" -o snapshot.png
```

### Example 3: Get Events for Specific Camera in Date Range

```bash
curl "http://localhost:8069/api/events?camera_id=camera-1&start_time=2024-03-15T00:00:00&end_time=2024-03-15T23:59:59"
```

### Example 4: Get Event Statistics

```bash
curl "http://localhost:8069/api/events/stats"
```

## Snapshot Visualization

### Detection/Tracking Events
- Bounding boxes drawn with color-coded by class
- Labels show: class name, confidence, track ID (if available)
- Format: `class_name: confidence (ID:track_id)`

### Motion Events
- Red overlay on motion areas (30% opacity)
- Timestamp text in red at top-left
- Original frame visible underneath

### ANPR Events
- License plate highlighted with green box (thick border)
- Plate text displayed at top in green box
- Format: `Plate: LICENSE_PLATE (confidence)`

## Performance Considerations

1. **Snapshot Storage**: 
   - Each snapshot is typically 50-200KB (PNG format)
   - 1000 events/day ≈ 50-200MB/day
   - Monitor disk usage and implement cleanup policies as needed

2. **Database Performance**:
   - Indexed queries are fast even with millions of records
   - Consider partitioning by date for very large datasets
   - Regular vacuum and analyze recommended for PostgreSQL

3. **API Response Times**:
   - List events: < 100ms for typical queries
   - Get snapshot: < 50ms (depends on disk I/O)
   - Stats endpoint: < 200ms (with proper indexes)

## Integration with Django

The events API can be easily integrated with your Django VMS application:

```python
import requests

class AnalyticsClient:
    def __init__(self, base_url="http://localhost:8069"):
        self.base_url = base_url
    
    def get_events(self, camera_id=None, event_type=None, **kwargs):
        """Get events with filters."""
        params = {"camera_id": camera_id, "event_type": event_type, **kwargs}
        response = requests.get(f"{self.base_url}/api/events", params=params)
        return response.json()
    
    def get_snapshot(self, event_id):
        """Download snapshot for an event."""
        response = requests.get(f"{self.base_url}/api/events/{event_id}/snapshot")
        return response.content  # Binary PNG data
    
    def get_stats(self, camera_id=None):
        """Get event statistics."""
        params = {"camera_id": camera_id} if camera_id else {}
        response = requests.get(f"{self.base_url}/api/events/stats", params=params)
        return response.json()
```

## Troubleshooting

### Issue: Snapshots not being saved
- Check `ENABLE_SNAPSHOTS` environment variable is `true`
- Verify snapshot directory is writable: `ls -la /app/snapshots`
- Check logs for snapshot errors

### Issue: Database connection failed
- Verify postgres container is running: `docker ps`
- Check database URL is correct
- Ensure database `vms_analytics_db` exists

### Issue: Snapshot not found (404)
- Verify snapshot path exists in file system
- Check if snapshot was deleted manually
- Review database record for correct path

## Future Enhancements

1. **Snapshot Retention Policies**: Automatic cleanup of old snapshots
2. **Thumbnail Generation**: Smaller preview images for faster loading
3. **Video Clips**: Save short video clips instead of single frames
4. **Cloud Storage**: S3/Azure Blob storage integration
5. **Advanced Search**: Search by object class, confidence range, etc.
6. **Batch Operations**: Delete multiple events, export functionality

## Database Migration

If you need to modify the database schema in the future, use Alembic:

```bash
# Generate migration
alembic revision --autogenerate -m "description"

# Apply migration
alembic upgrade head

# Rollback migration
alembic downgrade -1
```

## Maintenance

### Backup Recommendations

1. **Database Backup** (daily):
```bash
docker exec vms_db pg_dump -U vms_admin vms_analytics_db > backup_$(date +%Y%m%d).sql
```

2. **Snapshot Backup** (weekly):
```bash
docker run --rm -v analytics_snapshots:/data -v $(pwd):/backup \
  alpine tar czf /backup/snapshots_$(date +%Y%m%d).tar.gz /data
```

### Cleanup Old Events

```sql
-- Delete events older than 90 days
DELETE FROM events WHERE timestamp < NOW() - INTERVAL '90 days';

-- Vacuum to reclaim space
VACUUM ANALYZE events;
```

---

**Note**: All timestamps in the API are in UTC timezone. Make sure to convert to local timezone in your frontend application.

