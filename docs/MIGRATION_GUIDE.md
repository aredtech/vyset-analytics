# Migration Guide: Time-Based to Tracking-Based Filtering

## Overview

This guide helps you migrate from the old time-based event filtering to the new ByteTrack-based object tracking system.

## Breaking Changes

### 1. Event Structure Changed

#### Old Event (DetectionEvent)
```json
{
  "event_type": "detection",
  "camera_id": "cam-001",
  "timestamp": "2025-10-09T13:29:12Z",
  "detections": [
    {
      "class_name": "person",
      "confidence": 0.95,
      "bounding_box": {"x": 0.1, "y": 0.2, "width": 0.3, "height": 0.4}
    }
  ],
  "frame_number": 1000,
  "model_info": {"model_type": "yolov8n", "version": "8.1.0"}
}
```

#### New Event (TrackingEvent)
```json
{
  "event_type": "tracking",
  "camera_id": "cam-001",
  "timestamp": "2025-10-09T13:29:12Z",
  "track_id": 42,
  "tracking_action": "entered",
  "class_name": "person",
  "confidence": 0.95,
  "bounding_box": {"x": 0.1, "y": 0.2, "width": 0.3, "height": 0.4},
  "frame_number": 1000,
  "dwell_time_seconds": null,
  "model_info": {"model_type": "yolov8n", "version": "8.1.0"}
}
```

### 2. Event Frequency Changed

**Before:**
- Events published based on cooldown periods
- Continuous events while objects present (if cooldown expired)
- One event could contain multiple detections

**After:**
- Events only on entry/exit (lifecycle changes)
- No events while object remains in view
- One event per object per lifecycle change

### 3. Configuration Parameters Changed

#### Removed Parameters
- `detection_cooldown_seconds` - No longer used
- `detection_change_threshold` - No longer used

#### New Parameters
- `enable_object_tracking` (default: true)
- `track_buffer_frames` (default: 30)
- `min_dwell_time_seconds` (default: 1.0)
- `tracking_confidence_threshold` (default: 0.3)

## Update Your Code

### Consumer Code Updates

#### Old Code (DetectionEvent)
```python
import redis
import json

r = redis.Redis(host='localhost', port=6379, db=0)

while True:
    messages = r.xread({'stream:events': '$'}, block=1000)
    for stream, events in messages:
        for event_id, data in events:
            event = json.loads(data[b'data'])
            
            if event['event_type'] == 'detection':
                # Process all detections in the event
                for detection in event['detections']:
                    class_name = detection['class_name']
                    confidence = detection['confidence']
                    print(f"Detected {class_name} with {confidence:.2f}")
```

#### New Code (TrackingEvent)
```python
import redis
import json

r = redis.Redis(host='localhost', port=6379, db=0)

# Track active objects for counting
active_objects = {}

while True:
    messages = r.xread({'stream:events': '$'}, block=1000)
    for stream, events in messages:
        for event_id, data in events:
            event = json.loads(data[b'data'])
            
            if event['event_type'] == 'tracking':
                track_id = event['track_id']
                class_name = event['class_name']
                action = event['tracking_action']
                
                if action == 'entered':
                    # Object entered the scene
                    active_objects[track_id] = class_name
                    print(f"{class_name} entered (ID: {track_id})")
                    print(f"Current count: {len(active_objects)}")
                
                elif action == 'left':
                    # Object left the scene
                    dwell_time = event.get('dwell_time_seconds', 0)
                    print(f"{class_name} left (ID: {track_id}, stayed {dwell_time:.1f}s)")
                    
                    if track_id in active_objects:
                        del active_objects[track_id]
                    print(f"Current count: {len(active_objects)}")
```

### Database Schema Updates

If you're storing events in a database, update your schema:

#### Old Schema
```sql
CREATE TABLE detection_events (
    id SERIAL PRIMARY KEY,
    camera_id VARCHAR(255),
    timestamp TIMESTAMP,
    event_type VARCHAR(50),
    frame_number INTEGER,
    model_type VARCHAR(100),
    model_version VARCHAR(50)
);

CREATE TABLE detections (
    id SERIAL PRIMARY KEY,
    event_id INTEGER REFERENCES detection_events(id),
    class_name VARCHAR(100),
    confidence FLOAT,
    bbox_x FLOAT,
    bbox_y FLOAT,
    bbox_width FLOAT,
    bbox_height FLOAT
);
```

#### New Schema
```sql
CREATE TABLE tracking_events (
    id SERIAL PRIMARY KEY,
    camera_id VARCHAR(255),
    timestamp TIMESTAMP,
    event_type VARCHAR(50),
    track_id INTEGER,
    tracking_action VARCHAR(50),  -- 'entered' or 'left'
    class_name VARCHAR(100),
    confidence FLOAT,
    bbox_x FLOAT,
    bbox_y FLOAT,
    bbox_width FLOAT,
    bbox_height FLOAT,
    frame_number INTEGER,
    dwell_time_seconds FLOAT,
    model_type VARCHAR(100),
    model_version VARCHAR(50),
    UNIQUE(camera_id, track_id, tracking_action)
);

-- Index for fast queries
CREATE INDEX idx_tracking_camera_time ON tracking_events(camera_id, timestamp);
CREATE INDEX idx_tracking_action ON tracking_events(tracking_action);
CREATE INDEX idx_tracking_class ON tracking_events(class_name);
```

## Use Cases

### 1. Real-Time People Counting

```python
def get_current_count(camera_id: str) -> int:
    """Get current number of people in camera view."""
    entered = db.query(
        "SELECT COUNT(*) FROM tracking_events "
        "WHERE camera_id = %s AND tracking_action = 'entered' AND timestamp > NOW() - INTERVAL '1 hour'",
        (camera_id,)
    )[0]
    
    left = db.query(
        "SELECT COUNT(*) FROM tracking_events "
        "WHERE camera_id = %s AND tracking_action = 'left' AND timestamp > NOW() - INTERVAL '1 hour'",
        (camera_id,)
    )[0]
    
    return entered - left
```

### 2. Average Dwell Time

```python
def get_average_dwell_time(camera_id: str, class_name: str = "person") -> float:
    """Get average time objects spend in view."""
    result = db.query(
        "SELECT AVG(dwell_time_seconds) FROM tracking_events "
        "WHERE camera_id = %s AND class_name = %s AND tracking_action = 'left' "
        "AND timestamp > NOW() - INTERVAL '1 day'",
        (camera_id, class_name)
    )
    return result[0] or 0.0
```

### 3. Loitering Detection

```python
def get_loiterers(camera_id: str, min_dwell_seconds: float = 300) -> list:
    """Get objects that stayed longer than threshold."""
    return db.query(
        "SELECT track_id, class_name, dwell_time_seconds FROM tracking_events "
        "WHERE camera_id = %s AND tracking_action = 'left' "
        "AND dwell_time_seconds > %s "
        "AND timestamp > NOW() - INTERVAL '1 hour'",
        (camera_id, min_dwell_seconds)
    )
```

### 4. Traffic Flow Analysis

```python
def get_hourly_traffic(camera_id: str, hours: int = 24) -> dict:
    """Get hourly entry/exit counts."""
    results = db.query(
        "SELECT "
        "  DATE_TRUNC('hour', timestamp) as hour, "
        "  tracking_action, "
        "  COUNT(*) as count "
        "FROM tracking_events "
        "WHERE camera_id = %s AND timestamp > NOW() - INTERVAL '%s hours' "
        "GROUP BY hour, tracking_action "
        "ORDER BY hour",
        (camera_id, hours)
    )
    
    traffic = {}
    for row in results:
        hour = row[0]
        action = row[1]
        count = row[2]
        
        if hour not in traffic:
            traffic[hour] = {'entered': 0, 'left': 0}
        traffic[hour][action] = count
    
    return traffic
```

## Configuration Examples

### Minimal Configuration (Default Tracking)

```json
{
  "camera_id": "entrance-cam",
  "stream_url": "rtsp://camera/stream",
  "parameters": {
    "enable_object_detection": true,
    "enable_object_tracking": true,
    "detection_classes": ["person", "car"]
  }
}
```

### Advanced Configuration

```json
{
  "camera_id": "entrance-cam",
  "stream_url": "rtsp://camera/stream",
  "parameters": {
    "enable_object_detection": true,
    "enable_object_tracking": true,
    
    "detection_classes": ["person", "car", "truck"],
    "confidence_threshold": 0.5,
    "tracking_confidence_threshold": 0.3,
    
    "track_buffer_frames": 30,
    "min_dwell_time_seconds": 2.0,
    
    "frame_skip": 2,
    "max_fps": 15
  }
}
```

### Disable Tracking (Fallback to Detection Only)

```json
{
  "camera_id": "test-cam",
  "stream_url": "rtsp://camera/stream",
  "parameters": {
    "enable_object_detection": true,
    "enable_object_tracking": false
  }
}
```

**Note:** When tracking is disabled, no events will be published! You'll need to implement your own event logic.

## Testing Your Migration

### 1. Test Event Reception

```bash
# Subscribe to Redis stream
redis-cli
XREAD BLOCK 0 STREAMS stream:events $

# In another terminal, register a camera
curl -X POST http://localhost:8069/api/cameras \
  -H "Content-Type: application/json" \
  -d '[{
    "camera_id": "test-cam",
    "stream_url": "rtsp://your-camera",
    "parameters": {
      "enable_object_detection": true,
      "enable_object_tracking": true
    }
  }]'

# Wait for someone to walk in front of camera
# You should see "entered" and "left" events
```

### 2. Verify Event Structure

```python
import redis
import json

r = redis.Redis()
messages = r.xread({'stream:events': '0'}, count=1)

for stream, events in messages:
    for event_id, data in events:
        event = json.loads(data[b'data'])
        
        # Verify new structure
        assert event['event_type'] == 'tracking'
        assert 'track_id' in event
        assert 'tracking_action' in event
        assert event['tracking_action'] in ['entered', 'left']
        
        if event['tracking_action'] == 'left':
            assert 'dwell_time_seconds' in event
        
        print("✅ Event structure valid")
```

### 3. Test Counting Logic

```python
# Test that entries and exits balance
def test_counting():
    r = redis.Redis()
    messages = r.xread({'stream:events': '0'}, count=1000)
    
    counts = {}
    for stream, events in messages:
        for event_id, data in events:
            event = json.loads(data[b'data'])
            
            if event['event_type'] == 'tracking':
                camera_id = event['camera_id']
                action = event['tracking_action']
                
                if camera_id not in counts:
                    counts[camera_id] = {'entered': 0, 'left': 0}
                
                counts[camera_id][action] += 1
    
    # Verify counts are reasonable
    for camera_id, count in counts.items():
        entered = count['entered']
        left = count['left']
        current = entered - left
        
        print(f"{camera_id}: {entered} entered, {left} left, {current} current")
        
        # Current count should be reasonable
        assert current >= 0, "More exits than entries!"
```

## Performance Considerations

### CPU Usage
- **Overhead:** +5-10% per camera (ByteTrack is efficient)
- **Acceptable** for most deployments

### Memory Usage
- **~50MB per camera** for tracking state
- Grows with simultaneous objects
- Automatic cleanup

### Event Volume
- **Significantly reduced** compared to time-based
- Only entry/exit events (not continuous)
- Example: Person standing 10 seconds = 2 events (was 2-10 events)

## Troubleshooting

### Issue: No Events Being Published

**Possible causes:**
1. Tracking disabled (`enable_object_tracking: false`)
2. `min_dwell_time_seconds` too high
3. Objects not detected (confidence too low)

**Solution:**
```json
{
  "parameters": {
    "enable_object_tracking": true,
    "min_dwell_time_seconds": 0.5,  // Lower threshold
    "confidence_threshold": 0.3,     // Lower confidence
    "tracking_confidence_threshold": 0.2
  }
}
```

### Issue: Too Many "Left" Events

**Possible cause:** `track_buffer_frames` too low

**Solution:**
```json
{
  "parameters": {
    "track_buffer_frames": 60  // Wait 2 seconds at 30 FPS
  }
}
```

### Issue: Missing "Entered" Events

**Possible cause:** Objects already in view when camera starts

**Note:** Objects present when tracking starts won't generate "entered" events. This is expected behavior.

### Issue: Duplicate Track IDs

**Possible cause:** Camera restarted

**Note:** Track IDs reset when camera restarts. This is expected behavior. Use `(camera_id, track_id, timestamp)` as unique key.

## Rollback Plan

If you need to rollback to time-based filtering:

1. **Backup your current code:**
```bash
git stash
```

2. **Checkout previous version:**
```bash
git log --oneline  # Find commit before tracking
git checkout <commit-hash>
```

3. **Redeploy service:**
```bash
docker compose down
docker compose up --build
```

## Support

For issues or questions:
- Check logs: `docker compose logs -f analytics-service`
- Review [TRACKING_IMPLEMENTATION_STATUS.md](TRACKING_IMPLEMENTATION_STATUS.md)
- Review [OBJECT_TRACKING_PROPOSAL.md](OBJECT_TRACKING_PROPOSAL.md)

## Summary Checklist

- [ ] Update event consumers to handle `TrackingEvent`
- [ ] Update database schema if storing events
- [ ] Update camera configurations with new parameters
- [ ] Test entry/exit event detection
- [ ] Verify counting logic
- [ ] Monitor CPU/memory usage
- [ ] Update documentation for API users
- [ ] Train team on new event structure

---

**Migration completed successfully? Great! You now have more accurate event detection with object tracking! 🎉**

