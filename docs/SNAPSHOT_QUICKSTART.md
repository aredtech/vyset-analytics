# Snapshot Feature Quick Start Guide

## Overview

This guide will help you quickly get started with the new snapshot and events API feature.

## What's New?

✅ **Automatic Snapshot Capture** - Every event (motion, detection, ANPR) now saves a snapshot  
✅ **PostgreSQL Storage** - All events stored in database for querying  
✅ **REST API** - Query events, filter by camera/type/date, download snapshots  
✅ **Bounding Box Visualization** - Snapshots include drawn bounding boxes  
✅ **Persistent Storage** - Docker volumes ensure data survives restarts  

## Quick Setup

### 1. Start the Services

```bash
cd /Users/rajumandal/OldFiles/VMS2.0/analytics
docker compose up --build
```

This will start:
- **analytics-service** (FastAPI on port 8069)
- **db** (PostgreSQL on port 5432)
- Create volumes for snapshots and database

### 2. Verify Services are Running

```bash
# Check health
curl http://localhost:8069/api/health

# Expected response:
{
  "status": "healthy",
  "redis_connected": true,
  "active_cameras": 0
}
```

### 3. Register a Camera

```bash
curl -X POST http://localhost:8069/api/cameras \
  -H "Content-Type: application/json" \
  -d '[{
    "camera_id": "test-camera",
    "stream_url": "rtsp://your-camera-url",
    "parameters": {
      "enable_object_detection": true,
      "enable_motion_detection": true,
      "enable_anpr": false
    }
  }]'
```

### 4. Wait for Events

As events are detected, they will be:
1. Published to Redis (real-time)
2. Saved to PostgreSQL database
3. Snapshots saved to `/app/snapshots` volume

### 5. Query Events

```bash
# Get recent events
curl "http://localhost:8069/api/events?page=1&page_size=10"

# Filter by camera
curl "http://localhost:8069/api/events?camera_id=test-camera"

# Filter by event type
curl "http://localhost:8069/api/events?event_type=motion"

# Get statistics
curl "http://localhost:8069/api/events/stats"
```

### 6. Download Snapshots

```bash
# Get event list and find an event ID
EVENT_ID=$(curl -s "http://localhost:8069/api/events?page=1&page_size=1" | jq -r '.events[0].id')

# Download snapshot
curl "http://localhost:8069/api/events/${EVENT_ID}/snapshot" -o snapshot.png

# View the image
open snapshot.png  # macOS
xdg-open snapshot.png  # Linux
```

## Testing with Python Script

Run the included test script:

```bash
# Install dependencies (if not using Docker)
pip install requests

# Run test script
python examples/test_snapshots.py
```

This will:
- Test all API endpoints
- Download sample snapshots to `./downloaded_snapshots/`
- Show statistics and recent events

## Common Use Cases

### 1. Get Today's Motion Events

```bash
START_TIME=$(date -u +"%Y-%m-%dT00:00:00")
END_TIME=$(date -u +"%Y-%m-%dT23:59:59")

curl "http://localhost:8069/api/events?event_type=motion&start_time=${START_TIME}&end_time=${END_TIME}"
```

### 2. Get Events from Specific Camera in Last Hour

```bash
START_TIME=$(date -u -v-1H +"%Y-%m-%dT%H:%M:%S")  # macOS
# or
START_TIME=$(date -u -d '1 hour ago' +"%Y-%m-%dT%H:%M:%S")  # Linux

curl "http://localhost:8069/api/events?camera_id=test-camera&start_time=${START_TIME}"
```

### 3. Download All Snapshots from an Event

```python
import requests

# Get events
response = requests.get("http://localhost:8069/api/events?page_size=10")
events = response.json()["events"]

# Download each snapshot
for event in events:
    if event["snapshot_path"]:
        snapshot = requests.get(f"http://localhost:8069/api/events/{event['id']}/snapshot")
        with open(f"snapshot_{event['id']}.png", "wb") as f:
            f.write(snapshot.content)
        print(f"Downloaded snapshot for event {event['id']}")
```

## Integration with Django

Add to your Django views:

```python
import requests
from django.conf import settings

ANALYTICS_URL = settings.ANALYTICS_API_URL  # e.g., "http://analytics-service:8069"

def get_camera_events(camera_id, event_type=None, hours=24):
    """Get events for a camera."""
    from datetime import datetime, timedelta
    
    start_time = (datetime.utcnow() - timedelta(hours=hours)).isoformat()
    
    params = {
        "camera_id": camera_id,
        "start_time": start_time,
        "page_size": 100
    }
    
    if event_type:
        params["event_type"] = event_type
    
    response = requests.get(f"{ANALYTICS_URL}/api/events", params=params)
    return response.json()

def get_event_snapshot(event_id):
    """Get snapshot image for an event."""
    response = requests.get(f"{ANALYTICS_URL}/api/events/{event_id}/snapshot")
    return response.content  # Binary PNG data

# In your view
def event_detail(request, event_id):
    # Get event data
    response = requests.get(f"{ANALYTICS_URL}/api/events/{event_id}")
    event = response.json()
    
    # Get snapshot URL
    snapshot_url = f"{ANALYTICS_URL}/api/events/{event_id}/snapshot"
    
    return render(request, "event_detail.html", {
        "event": event,
        "snapshot_url": snapshot_url
    })
```

In your Django template:

```html
<div class="event-card">
    <h3>{{ event.event_type|title }} Event</h3>
    <p>Camera: {{ event.camera_id }}</p>
    <p>Time: {{ event.timestamp }}</p>
    
    {% if event.snapshot_path %}
    <img src="{{ snapshot_url }}" alt="Event Snapshot" class="event-snapshot">
    {% endif %}
    
    <pre>{{ event.event_data|json_script }}</pre>
</div>
```

## Docker Volume Management

### View Snapshots Directory

```bash
# List snapshots
docker exec analytics-service ls -lh /app/snapshots

# View specific camera's snapshots
docker exec analytics-service ls -lh /app/snapshots/test-camera/
```

### Backup Snapshots

```bash
# Create backup
docker run --rm \
  -v analytics_snapshots:/data \
  -v $(pwd):/backup \
  alpine tar czf /backup/snapshots_backup.tar.gz /data

# Restore backup
docker run --rm \
  -v analytics_snapshots:/data \
  -v $(pwd):/backup \
  alpine tar xzf /backup/snapshots_backup.tar.gz -C /
```

### Database Backup

```bash
# Backup database
docker exec vms_db pg_dump -U vms_admin vms_analytics_db > backup.sql

# Restore database
cat backup.sql | docker exec -i vms_db psql -U vms_admin vms_analytics_db
```

## Monitoring

### Check Database Size

```bash
docker exec vms_db psql -U vms_admin vms_analytics_db -c "
SELECT 
  COUNT(*) as total_events,
  pg_size_pretty(pg_database_size('vms_analytics_db')) as db_size
FROM events;
"
```

### Check Snapshot Storage

```bash
docker exec analytics-service du -sh /app/snapshots
```

### View Recent Events

```bash
docker exec vms_db psql -U vms_admin vms_analytics_db -c "
SELECT 
  event_type,
  camera_id,
  timestamp,
  snapshot_path IS NOT NULL as has_snapshot
FROM events
ORDER BY timestamp DESC
LIMIT 10;
"
```

## Troubleshooting

### Issue: No events in database

**Check:**
1. Is the analytics service running? `docker ps`
2. Is a camera registered? `curl http://localhost:8069/api/cameras`
3. Is the camera stream accessible?
4. Check logs: `docker logs analytics-service`

### Issue: Snapshots not being saved

**Check:**
1. Is `ENABLE_SNAPSHOTS=true` in environment?
2. Is the snapshots directory writable?
3. Check logs for snapshot errors

**Fix:**
```bash
# Verify snapshots directory
docker exec analytics-service ls -la /app/snapshots

# Check environment
docker exec analytics-service env | grep SNAPSHOT
```

### Issue: Cannot download snapshot (404)

**Check:**
1. Does the event have a snapshot? Check `snapshot_path` field
2. Does the file exist?

```bash
# Check if file exists
EVENT_ID=123
docker exec analytics-service ls -lh /app/snapshots/path/to/snapshot.png
```

### Issue: Database connection failed

**Check:**
1. Is postgres container running? `docker ps | grep vms_db`
2. Is the database created?

```bash
# Check database exists
docker exec vms_db psql -U vms_admin -l | grep vms_analytics_db

# Create database manually if needed
docker exec vms_db psql -U vms_admin -c "CREATE DATABASE vms_analytics_db;"
```

## Performance Tips

1. **Snapshot Storage**: Each snapshot is ~50-200KB. Monitor disk usage.
2. **Database Cleanup**: Implement regular cleanup for old events:
   ```sql
   DELETE FROM events WHERE timestamp < NOW() - INTERVAL '90 days';
   ```
3. **Pagination**: Always use pagination for large result sets
4. **Indexes**: Database is indexed on camera_id, event_type, and timestamp

## Next Steps

- Read [SNAPSHOT_FEATURE.md](SNAPSHOT_FEATURE.md) for detailed API documentation
- Implement cleanup policies for old events/snapshots
- Integrate with your Django frontend
- Set up automated backups
- Configure monitoring and alerts

## Support

For issues or questions:
1. Check logs: `docker logs analytics-service`
2. Review documentation: [SNAPSHOT_FEATURE.md](SNAPSHOT_FEATURE.md)
3. Test with: `python examples/test_snapshots.py`

---

Happy tracking! 📸

