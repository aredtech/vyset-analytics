# Redis Pub/Sub Implementation

## Overview

The analytics service now uses **Redis Pub/Sub** for real-time event distribution while maintaining database persistence for all events. This architecture provides:

1. **Real-time notifications**: Consumers receive events instantly as they occur
2. **Database persistence**: All events are stored in PostgreSQL for historical queries
3. **Latest data only**: Pub/Sub doesn't buffer old messages - consumers only receive events from when they connect forward
4. **Same data structure**: Event data structure remains unchanged

## Architecture

### Event Flow

```
Camera Frame → Detection/Motion/ANPR → Save to Database → Publish to Redis Pub/Sub → Consumers
                                              ↓
                                    EventRecord (PostgreSQL)
```

Every event follows this process:

1. **Detection**: Frame is processed by detector (object tracking, motion, ANPR)
2. **Database Save**: Event is saved to PostgreSQL with:
   - Event metadata (type, camera_id, timestamp, frame_number)
   - Snapshot path (if snapshot was saved)
   - Event-specific data (tracking info, motion metrics, license plate, etc.)
3. **Pub/Sub Publish**: After successful database save, event is published to Redis channel
4. **Consumer Receipt**: All subscribed consumers receive the event immediately

### Key Benefits

- **Pub/Sub**: Instant delivery to consumers (no polling needed)
- **Database**: Complete event history and queryable data
- **Reliability**: Events are persisted even if no consumers are listening
- **Scalability**: Multiple consumers can subscribe independently

## Event Types

All event types are saved to database and published to Redis Pub/Sub:

### 1. Tracking Events

Object tracking lifecycle events (entered, left, updated).

**Event Data Structure:**
```json
{
  "id": 123,
  "event_type": "tracking",
  "camera_id": "camera-01",
  "timestamp": "2024-10-11T12:34:56.789Z",
  "frame_number": 1234,
  "snapshot_path": "snapshots/2024-10-11/camera-01/detection_1234_1728649696.png",
  "event_data": {
    "track_id": 15,
    "tracking_action": "entered",
    "class_name": "person",
    "confidence": 0.95,
    "bounding_box": {
      "x": 0.1,
      "y": 0.2,
      "width": 0.3,
      "height": 0.4
    },
    "dwell_time_seconds": null,
    "model_info": {
      "model_type": "YOLOv8",
      "version": "yolov8n.pt"
    }
  },
  "created_at": "2024-10-11T12:34:56.789123"
}
```

### 2. Motion Events

Motion detection events.

**Event Data Structure:**
```json
{
  "id": 124,
  "event_type": "motion",
  "camera_id": "camera-01",
  "timestamp": "2024-10-11T12:35:00.123Z",
  "frame_number": 1240,
  "snapshot_path": "snapshots/2024-10-11/camera-01/motion_1240_1728649700.png",
  "event_data": {
    "motion_intensity": 0.75,
    "affected_area_percentage": 15.5
  },
  "created_at": "2024-10-11T12:35:00.123456"
}
```

### 3. ANPR Events

Automatic Number Plate Recognition events.

**Event Data Structure:**
```json
{
  "id": 125,
  "event_type": "anpr",
  "camera_id": "camera-02",
  "timestamp": "2024-10-11T12:36:00.456Z",
  "frame_number": 2100,
  "snapshot_path": "snapshots/2024-10-11/camera-02/anpr_2100_1728649760.png",
  "event_data": {
    "anpr_result": {
      "license_plate": "ABC123",
      "confidence": 0.92,
      "region": "CA"
    }
  },
  "created_at": "2024-10-11T12:36:00.456789"
}
```

## Consumer Implementation

### Python Example

See `examples/pubsub_consumer_example.py` for a complete implementation.

**Basic Consumer:**

```python
import redis
import json

# Connect to Redis
client = redis.Redis(host='localhost', port=6379, decode_responses=True)
pubsub = client.pubsub()

# Subscribe to events channel
pubsub.subscribe('events')

# Listen for events
for message in pubsub.listen():
    if message['type'] == 'message':
        event = json.loads(message['data'])
        print(f"Received {event['event_type']} event from {event['camera_id']}")
        # Process event...
```

### Node.js Example

```javascript
const redis = require('redis');

const client = redis.createClient({
  host: 'localhost',
  port: 6379
});

client.on('message', (channel, message) => {
  const event = JSON.parse(message);
  console.log(`Received ${event.event_type} event from ${event.camera_id}`);
  // Process event...
});

client.subscribe('events');
```

### Go Example

```go
package main

import (
    "encoding/json"
    "fmt"
    "github.com/go-redis/redis/v8"
)

func main() {
    client := redis.NewClient(&redis.Options{
        Addr: "localhost:6379",
    })
    
    pubsub := client.Subscribe(ctx, "events")
    
    for msg := range pubsub.Channel() {
        var event map[string]interface{}
        json.Unmarshal([]byte(msg.Payload), &event)
        fmt.Printf("Received %s event from %s\n", 
            event["event_type"], event["camera_id"])
        // Process event...
    }
}
```

## Database Schema

All events are stored in the `events` table:

```sql
CREATE TABLE events (
    id SERIAL PRIMARY KEY,
    event_type VARCHAR(50) NOT NULL,
    camera_id VARCHAR(100) NOT NULL,
    timestamp TIMESTAMP NOT NULL,
    frame_number INTEGER NOT NULL,
    snapshot_path VARCHAR(500),
    event_data JSONB NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- Indexes for common queries
CREATE INDEX idx_camera_timestamp ON events(camera_id, timestamp);
CREATE INDEX idx_event_type_timestamp ON events(event_type, timestamp);
CREATE INDEX idx_event_type ON events(event_type);
CREATE INDEX idx_camera_id ON events(camera_id);
CREATE INDEX idx_timestamp ON events(timestamp);
```

## API Endpoints

The REST API remains available for querying historical events:

### List Events
```
GET /api/events
```

**Query Parameters:**
- `camera_id`: Filter by camera ID
- `event_type`: Filter by type (tracking, motion, anpr)
- `start_time`: Start timestamp (ISO format)
- `end_time`: End timestamp (ISO format)
- `page`: Page number (default: 1)
- `page_size`: Items per page (default: 50, max: 500)

**Example:**
```bash
curl "http://localhost:8069/api/events?camera_id=camera-01&event_type=tracking&page=1&page_size=50"
```

### Get Event by ID
```
GET /api/events/{event_id}
```

### Get Event Snapshot
```
GET /api/events/{event_id}/snapshot
```

### Event Statistics
```
GET /api/events/stats
```

## Configuration

Configuration is managed through environment variables or `.env` file:

```env
# Redis Configuration
REDIS_HOST=redis
REDIS_PORT=6379
REDIS_DB=0
REDIS_CHANNEL_NAME=events

# Database Configuration
DATABASE_URL=postgresql://user:password@host:5432/database

# Snapshot Configuration
SNAPSHOTS_DIR=/app/snapshots
ENABLE_SNAPSHOTS=true
```

## Running the Consumer Example

1. **Install dependencies:**
```bash
pip install redis
```

2. **Run the consumer:**
```bash
python examples/pubsub_consumer_example.py
```

3. **Configure connection (optional):**
Edit the configuration section in the script:
```python
REDIS_HOST = 'localhost'  # or your Redis host
REDIS_PORT = 6379
CHANNEL_NAME = 'events'
```

## Monitoring

### Check Redis Pub/Sub

**Monitor channel activity:**
```bash
redis-cli PUBSUB CHANNELS
```

**Monitor active subscriptions:**
```bash
redis-cli PUBSUB NUMSUB events
```

**Monitor all messages (for debugging):**
```bash
redis-cli PSUBSCRIBE '*'
```

### Check Database

**Count events by type:**
```sql
SELECT event_type, COUNT(*) 
FROM events 
GROUP BY event_type;
```

**Recent events:**
```sql
SELECT id, event_type, camera_id, timestamp 
FROM events 
ORDER BY timestamp DESC 
LIMIT 10;
```

## Pub/Sub vs Stream Comparison

| Feature | Pub/Sub (Current) | Streams (Alternative) |
|---------|-------------------|----------------------|
| Delivery | Fire-and-forget | Persistent log |
| History | No | Yes (configurable) |
| Consumer Groups | No | Yes |
| Acknowledgment | No | Yes |
| Use Case | Real-time notifications | Event sourcing |
| Complexity | Simple | More complex |

We chose **Pub/Sub** because:
- ✅ Simple architecture
- ✅ Real-time delivery
- ✅ Database provides persistence
- ✅ Consumers only need latest events
- ✅ No need for consumer groups or acknowledgments

## Migration Notes

### Changes from Previous Implementation

1. **All events now saved to database**: Previously, tracking and motion events were only published to Redis
2. **Consistent event handling**: Single `save_and_publish_event()` function for all event types
3. **Event ID included**: Published events now include database ID
4. **Created_at timestamp**: Events include database creation timestamp

### Backward Compatibility

The event data structure remains the same, with additions:
- `id`: Database event ID (new)
- `created_at`: Database creation timestamp (new)

Existing consumers should continue to work, and can optionally use the new fields.

## Troubleshooting

### No events received by consumer

1. Check Redis connection:
```bash
redis-cli ping
```

2. Verify channel name matches configuration

3. Check if analytics service is running:
```bash
curl http://localhost:8069/
```

4. Monitor Redis Pub/Sub:
```bash
redis-cli MONITOR
```

### Events not saved to database

1. Check database connection in logs
2. Verify database credentials in configuration
3. Check PostgreSQL logs for errors

### Performance considerations

- Pub/Sub is very fast (sub-millisecond latency)
- Database writes are sequential and shouldn't impact performance
- Consider database indexes for query optimization
- Snapshot storage can consume disk space - implement cleanup policy

## Best Practices

1. **Error Handling**: Always handle connection errors in consumers
2. **Reconnection Logic**: Implement automatic reconnection if Redis disconnects
3. **Graceful Shutdown**: Handle signals (Ctrl+C) to close connections cleanly
4. **Multiple Consumers**: Each consumer can process events independently
5. **Filtering**: Filter events in consumer based on your needs (by camera, type, etc.)
6. **Database Queries**: Use REST API for historical data, Pub/Sub for real-time
7. **Monitoring**: Monitor subscriber count to ensure consumers are connected

## Future Enhancements

Potential improvements for future versions:

1. **Event Filtering**: Allow consumers to subscribe to specific event types or cameras
2. **Redis Streams**: Add optional Redis Streams support for event history
3. **Webhook Support**: HTTP callbacks for events
4. **Rate Limiting**: Configurable event rate limits per camera
5. **Compression**: Compress event data for large payloads
6. **Encryption**: Encrypt sensitive event data (e.g., license plates)

