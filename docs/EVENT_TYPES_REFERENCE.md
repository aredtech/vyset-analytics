# Event Types Reference - Complete Examples

This document provides complete JSON examples of all event types emitted by the analytics service. Use these for building parser functions and handling events in your backend.

---

## Event Types Overview

The analytics service emits 3 types of events:

1. **Tracking Events** - Object entry/exit with tracking IDs (NEW)
2. **Motion Events** - Motion detection
3. **ANPR Events** - License plate recognition

---

## 1. Tracking Events

### 1.1 Object Entered Event

Published when a new object enters the scene and is assigned a tracking ID.

```json
{
  "event_type": "tracking",
  "camera_id": "entrance-cam-01",
  "timestamp": "2025-10-09T14:23:45.123456Z",
  "track_id": 42,
  "tracking_action": "entered",
  "class_name": "person",
  "confidence": 0.9234567,
  "bounding_box": {
    "x": 0.125,
    "y": 0.2456,
    "width": 0.3125,
    "height": 0.4567
  },
  "frame_number": 1523,
  "dwell_time_seconds": null,
  "model_info": {
    "model_type": "yolov8n",
    "version": "8.1.0"
  }
}
```

### 1.2 Object Left Event

Published when an object leaves the scene (not detected for `track_buffer_frames` consecutive frames).

```json
{
  "event_type": "tracking",
  "camera_id": "entrance-cam-01",
  "timestamp": "2025-10-09T14:24:12.789012Z",
  "track_id": 42,
  "tracking_action": "left",
  "class_name": "person",
  "confidence": 0.0,
  "bounding_box": {
    "x": 0.725,
    "y": 0.3456,
    "width": 0.2875,
    "height": 0.4123
  },
  "frame_number": 2345,
  "dwell_time_seconds": 27.4,
  "model_info": {
    "model_type": "yolov8n",
    "version": "8.1.0"
  }
}
```

### 1.3 Multiple Objects - Car Example

```json
{
  "event_type": "tracking",
  "camera_id": "parking-lot-02",
  "timestamp": "2025-10-09T14:25:33.456789Z",
  "track_id": 156,
  "tracking_action": "entered",
  "class_name": "car",
  "confidence": 0.8891234,
  "bounding_box": {
    "x": 0.45,
    "y": 0.55,
    "width": 0.35,
    "height": 0.25
  },
  "frame_number": 3456,
  "dwell_time_seconds": null,
  "model_info": {
    "model_type": "yolov8n",
    "version": "8.1.0"
  }
}
```

### 1.4 Truck Example - Exit with Long Dwell Time

```json
{
  "event_type": "tracking",
  "camera_id": "loading-dock-03",
  "timestamp": "2025-10-09T15:15:22.111222Z",
  "track_id": 89,
  "tracking_action": "left",
  "class_name": "truck",
  "confidence": 0.0,
  "bounding_box": {
    "x": 0.15,
    "y": 0.25,
    "width": 0.55,
    "height": 0.65
  },
  "frame_number": 45678,
  "dwell_time_seconds": 1845.6,
  "model_info": {
    "model_type": "yolov8n",
    "version": "8.1.0"
  }
}
```

---

## 2. Motion Events

Published when motion is detected in the camera view.

### 2.1 Standard Motion Event

```json
{
  "event_type": "motion",
  "camera_id": "corridor-cam-05",
  "timestamp": "2025-10-09T14:26:45.678901Z",
  "motion_intensity": 0.7523456,
  "affected_area_percentage": 0.2345678,
  "frame_number": 4567
}
```

### 2.2 High Intensity Motion

```json
{
  "event_type": "motion",
  "camera_id": "entrance-cam-01",
  "timestamp": "2025-10-09T14:27:12.345678Z",
  "motion_intensity": 0.9512345,
  "affected_area_percentage": 0.8234567,
  "frame_number": 5234
}
```

### 2.3 Low Intensity Motion

```json
{
  "event_type": "motion",
  "camera_id": "warehouse-cam-12",
  "timestamp": "2025-10-09T14:28:33.987654Z",
  "motion_intensity": 0.2123456,
  "affected_area_percentage": 0.0512345,
  "frame_number": 6789
}
```

---

## 3. ANPR Events

Published when a license plate is detected and recognized.

### 3.1 License Plate with Region

```json
{
  "event_type": "anpr",
  "camera_id": "gate-cam-01",
  "timestamp": "2025-10-09T14:29:55.123456Z",
  "anpr_result": {
    "license_plate": "ABC1234",
    "confidence": 0.9123456,
    "region": "CA"
  },
  "frame_number": 7890
}
```

### 3.2 License Plate without Region

```json
{
  "event_type": "anpr",
  "camera_id": "parking-entrance-02",
  "timestamp": "2025-10-09T14:30:22.789012Z",
  "anpr_result": {
    "license_plate": "XYZ5678",
    "confidence": 0.8534567,
    "region": null
  },
  "frame_number": 8901
}
```

### 3.3 Low Confidence Plate Detection

```json
{
  "event_type": "anpr",
  "camera_id": "exit-cam-03",
  "timestamp": "2025-10-09T14:31:45.456789Z",
  "anpr_result": {
    "license_plate": "DEF9012",
    "confidence": 0.6789012,
    "region": "NY"
  },
  "frame_number": 9012
}
```

### 3.4 License Plate with Vehicle Class

```json
{
  "event_type": "anpr",
  "camera_id": "gate-cam-01",
  "timestamp": "2025-10-09T14:32:10.123456Z",
  "anpr_result": {
    "license_plate": "GHI3456",
    "confidence": 0.9234567,
    "region": "TX",
    "vehicle_class": "truck"
  },
  "frame_number": 9013
}
```

---

## Field Specifications

### Common Fields

| Field | Type | Description | Present In |
|-------|------|-------------|------------|
| `event_type` | string | Type of event: "tracking", "motion", or "anpr" | All events |
| `camera_id` | string | Unique camera identifier | All events |
| `timestamp` | string | ISO 8601 timestamp with 'Z' suffix (UTC) | All events |
| `frame_number` | integer | Frame number when event occurred | All events |

### Tracking Event Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `track_id` | integer | Yes | Unique tracking ID for the object |
| `tracking_action` | string | Yes | "entered" or "left" |
| `class_name` | string | Yes | Object class (e.g., "person", "car", "truck") |
| `confidence` | float | Yes | Detection confidence (0.0-1.0). Always 0.0 for "left" events |
| `bounding_box` | object | Yes | Normalized bounding box coordinates |
| `bounding_box.x` | float | Yes | Top-left X coordinate (0.0-1.0) |
| `bounding_box.y` | float | Yes | Top-left Y coordinate (0.0-1.0) |
| `bounding_box.width` | float | Yes | Width as fraction of frame (0.0-1.0) |
| `bounding_box.height` | float | Yes | Height as fraction of frame (0.0-1.0) |
| `dwell_time_seconds` | float or null | Yes | Time object was present. `null` for "entered", float for "left" |
| `model_info` | object | Yes | Model information |
| `model_info.model_type` | string | Yes | Model type (e.g., "yolov8n") |
| `model_info.version` | string | Yes | Model version (e.g., "8.1.0") |

### Motion Event Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `motion_intensity` | float | Yes | Motion intensity (0.0-1.0) |
| `affected_area_percentage` | float | Yes | Percentage of frame with motion (0.0-1.0) |

### ANPR Event Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `anpr_result` | object | Yes | ANPR detection result |
| `anpr_result.license_plate` | string | Yes | Detected license plate text |
| `anpr_result.confidence` | float | Yes | Recognition confidence (0.0-1.0) |
| `anpr_result.region` | string or null | Yes | Region/state code or null if not detected |
| `anpr_result.vehicle_class` | string or null | No | YOLO class of the vehicle (e.g., car, truck, bus, motorcycle) or null if not detected |

---

## Data Type Details

### Timestamps
- **Format:** ISO 8601 with microseconds and 'Z' suffix
- **Example:** `2025-10-09T14:23:45.123456Z`
- **Timezone:** Always UTC
- **Python generation:** `datetime.utcnow().isoformat() + "Z"`

### Floating Point Numbers
- All floats may have up to 7 decimal places
- Confidence values are always between 0.0 and 1.0
- Bounding box coordinates are normalized (0.0 to 1.0)
- Dwell time can be any non-negative float

### Bounding Boxes
- Coordinates are normalized to frame dimensions
- `x`, `y`: Top-left corner
- `width`, `height`: Box dimensions
- All values are fractions of the frame size (0.0-1.0)

### Track IDs
- Unique integer per object within a camera session
- Reset when camera restarts
- May be reused after cleanup
- Different cameras may have same track IDs

---

## Backend Parser Implementation

### Python Example

```python
from typing import Dict, Any, Optional, Union
from datetime import datetime
from enum import Enum

class EventType(Enum):
    TRACKING = "tracking"
    MOTION = "motion"
    ANPR = "anpr"

class TrackingAction(Enum):
    ENTERED = "entered"
    LEFT = "left"

def parse_event(event_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Parse and validate analytics event.
    
    Args:
        event_data: Raw event dictionary from Redis stream
        
    Returns:
        Parsed and validated event dictionary
        
    Raises:
        ValueError: If event is invalid
    """
    event_type = event_data.get("event_type")
    
    if event_type == EventType.TRACKING.value:
        return parse_tracking_event(event_data)
    elif event_type == EventType.MOTION.value:
        return parse_motion_event(event_data)
    elif event_type == EventType.ANPR.value:
        return parse_anpr_event(event_data)
    else:
        raise ValueError(f"Unknown event type: {event_type}")

def parse_tracking_event(event: Dict[str, Any]) -> Dict[str, Any]:
    """Parse tracking event."""
    return {
        "event_type": "tracking",
        "camera_id": event["camera_id"],
        "timestamp": datetime.fromisoformat(event["timestamp"].rstrip("Z")),
        "track_id": int(event["track_id"]),
        "tracking_action": event["tracking_action"],
        "class_name": event["class_name"],
        "confidence": float(event["confidence"]),
        "bounding_box": {
            "x": float(event["bounding_box"]["x"]),
            "y": float(event["bounding_box"]["y"]),
            "width": float(event["bounding_box"]["width"]),
            "height": float(event["bounding_box"]["height"]),
        },
        "frame_number": int(event["frame_number"]),
        "dwell_time_seconds": float(event["dwell_time_seconds"]) if event["dwell_time_seconds"] is not None else None,
        "model_info": {
            "model_type": event["model_info"]["model_type"],
            "version": event["model_info"]["version"],
        }
    }

def parse_motion_event(event: Dict[str, Any]) -> Dict[str, Any]:
    """Parse motion event."""
    return {
        "event_type": "motion",
        "camera_id": event["camera_id"],
        "timestamp": datetime.fromisoformat(event["timestamp"].rstrip("Z")),
        "motion_intensity": float(event["motion_intensity"]),
        "affected_area_percentage": float(event["affected_area_percentage"]),
        "frame_number": int(event["frame_number"]),
    }

def parse_anpr_event(event: Dict[str, Any]) -> Dict[str, Any]:
    """Parse ANPR event."""
    return {
        "event_type": "anpr",
        "camera_id": event["camera_id"],
        "timestamp": datetime.fromisoformat(event["timestamp"].rstrip("Z")),
        "anpr_result": {
            "license_plate": event["anpr_result"]["license_plate"],
            "confidence": float(event["anpr_result"]["confidence"]),
            "region": event["anpr_result"]["region"],
        },
        "frame_number": int(event["frame_number"]),
    }
```

### JavaScript/TypeScript Example

```typescript
// TypeScript types
interface BaseEvent {
  event_type: string;
  camera_id: string;
  timestamp: string;
  frame_number: number;
}

interface BoundingBox {
  x: number;
  y: number;
  width: number;
  height: number;
}

interface ModelInfo {
  model_type: string;
  version: string;
}

interface TrackingEvent extends BaseEvent {
  event_type: "tracking";
  track_id: number;
  tracking_action: "entered" | "left";
  class_name: string;
  confidence: number;
  bounding_box: BoundingBox;
  dwell_time_seconds: number | null;
  model_info: ModelInfo;
}

interface MotionEvent extends BaseEvent {
  event_type: "motion";
  motion_intensity: number;
  affected_area_percentage: number;
}

interface ANPREvent extends BaseEvent {
  event_type: "anpr";
  anpr_result: {
    license_plate: string;
    confidence: number;
    region: string | null;
  };
}

type AnalyticsEvent = TrackingEvent | MotionEvent | ANPREvent;

// Parser function
function parseEvent(eventData: any): AnalyticsEvent {
  switch (eventData.event_type) {
    case "tracking":
      return parseTrackingEvent(eventData);
    case "motion":
      return parseMotionEvent(eventData);
    case "anpr":
      return parseANPREvent(eventData);
    default:
      throw new Error(`Unknown event type: ${eventData.event_type}`);
  }
}

function parseTrackingEvent(data: any): TrackingEvent {
  return {
    event_type: "tracking",
    camera_id: data.camera_id,
    timestamp: data.timestamp,
    track_id: parseInt(data.track_id),
    tracking_action: data.tracking_action,
    class_name: data.class_name,
    confidence: parseFloat(data.confidence),
    bounding_box: {
      x: parseFloat(data.bounding_box.x),
      y: parseFloat(data.bounding_box.y),
      width: parseFloat(data.bounding_box.width),
      height: parseFloat(data.bounding_box.height),
    },
    frame_number: parseInt(data.frame_number),
    dwell_time_seconds: data.dwell_time_seconds !== null 
      ? parseFloat(data.dwell_time_seconds) 
      : null,
    model_info: {
      model_type: data.model_info.model_type,
      version: data.model_info.version,
    },
  };
}

function parseMotionEvent(data: any): MotionEvent {
  return {
    event_type: "motion",
    camera_id: data.camera_id,
    timestamp: data.timestamp,
    motion_intensity: parseFloat(data.motion_intensity),
    affected_area_percentage: parseFloat(data.affected_area_percentage),
    frame_number: parseInt(data.frame_number),
  };
}

function parseANPREvent(data: any): ANPREvent {
  return {
    event_type: "anpr",
    camera_id: data.camera_id,
    timestamp: data.timestamp,
    anpr_result: {
      license_plate: data.anpr_result.license_plate,
      confidence: parseFloat(data.anpr_result.confidence),
      region: data.anpr_result.region,
    },
    frame_number: parseInt(data.frame_number),
  };
}
```

---

## Redis Stream Format

Events are published to Redis Streams (default: `stream:events`) with the following structure:

```
Stream: stream:events
Entry ID: 1696857825123-0
Fields:
  data: <JSON-serialized event>
```

### Reading Events from Redis (Python)

```python
import redis
import json

r = redis.Redis(host='localhost', port=6379, db=0)

# Read from stream
while True:
    messages = r.xread({'stream:events': '$'}, block=1000, count=10)
    
    for stream, events in messages:
        for event_id, fields in events:
            # Parse JSON from 'data' field
            event = json.loads(fields[b'data'])
            
            # Process event
            event_type = event['event_type']
            camera_id = event['camera_id']
            
            if event_type == 'tracking':
                handle_tracking_event(event)
            elif event_type == 'motion':
                handle_motion_event(event)
            elif event_type == 'anpr':
                handle_anpr_event(event)
```

---

## Common Detection Classes

Objects that may appear in tracking events:

- `person` - Human
- `bicycle` - Bicycle
- `car` - Car/sedan
- `motorcycle` - Motorcycle
- `bus` - Bus
- `truck` - Truck
- `traffic light` - Traffic light
- `stop sign` - Stop sign
- `dog` - Dog
- `cat` - Cat
- `backpack` - Backpack
- `handbag` - Handbag
- `suitcase` - Suitcase

For complete list, see YOLO COCO dataset classes.

---

## Event Frequency Guidelines

### Tracking Events
- **Entry events:** One per object when first detected
- **Exit events:** One per object after `track_buffer_frames` (default: 30 frames ~1 second)
- **Typical rate:** 2-10 events per minute for moderate traffic

### Motion Events
- **Cooldown:** Default 2 seconds between events
- **Typical rate:** 0-30 events per minute depending on activity

### ANPR Events
- **Cooldown:** Default 3 seconds per license plate
- **Typical rate:** 0-20 events per minute in parking/gate scenarios

---

## Validation Checklist

When implementing your parser:

- [ ] Handle all three event types correctly
- [ ] Validate `event_type` field
- [ ] Parse timestamps as UTC
- [ ] Handle null values in optional fields (`dwell_time_seconds`, `region`)
- [ ] Validate confidence ranges (0.0-1.0)
- [ ] Validate bounding box coordinates (0.0-1.0)
- [ ] Handle missing fields gracefully
- [ ] Log parsing errors for debugging
- [ ] Test with all example events above

---

## Testing Your Parser

Use these test cases:

1. **Parse each example** from this document
2. **Validate all fields** are correctly extracted
3. **Test error handling** with malformed events
4. **Test null handling** for optional fields
5. **Test type conversions** (string to int, float, etc.)
6. **Performance test** with 1000+ events

---

## Support

For questions or issues:
- Review [TRACKING_IMPLEMENTATION_STATUS.md](TRACKING_IMPLEMENTATION_STATUS.md)
- Check [MIGRATION_GUIDE.md](MIGRATION_GUIDE.md)
- Examine Redis stream directly: `redis-cli XREAD STREAMS stream:events 0`

---

**Last Updated:** October 9, 2025  
**Analytics Service Version:** 2.0 (with ByteTrack tracking)

