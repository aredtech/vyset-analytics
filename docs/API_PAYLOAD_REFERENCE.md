# API Payload Reference - Complete Camera Configuration Examples

This document provides complete examples of all camera configuration payloads for the analytics service API. Use these for building your backend API integration and validation.

---

## API Endpoint

```
POST /api/cameras
Content-Type: application/json
```

---

## Payload Structure Overview

```json
[
  {
    "camera_id": "string (required)",
    "status": "active | inactive | error",
    "stream_url": "string (required)",
    "parameters": {
      // Detection settings
      // Tracking settings
      // Performance settings
      // Filtering settings
    }
  }
]
```

**Note:** Payload is an **array** of camera configurations.

---

## 1. Minimal Configuration

Minimal payload with only required fields (uses all defaults):

```json
[
  {
    "camera_id": "cam-001",
    "stream_url": "rtsp://192.168.1.100:554/stream"
  }
]
```

**Defaults applied:**
- `status`: "active"
- `enable_object_detection`: true
- `enable_object_tracking`: true
- `enable_motion_detection`: true
- `enable_anpr`: false
- All other parameters use default values

---

## 2. Standard Configuration

Typical configuration for people counting at entrance:

```json
[
  {
    "camera_id": "entrance-cam-01",
    "status": "active",
    "stream_url": "rtsp://admin:password@192.168.1.100:554/media/video1",
    "parameters": {
      "detection_classes": ["person"],
      "confidence_threshold": 0.5,
      "enable_motion_detection": true,
      "enable_object_detection": true,
      "enable_object_tracking": true,
      "enable_anpr": false,
      "frame_skip": 1,
      "max_fps": 30,
      "track_buffer_frames": 30,
      "min_dwell_time_seconds": 1.0,
      "tracking_confidence_threshold": 0.3,
      "motion_threshold": 0.1,
      "motion_cooldown_seconds": 2.0,
      "anpr_cooldown_seconds": 3.0
    }
  }
]
```

---

## 3. All Parameters with Default Values

Complete configuration showing all available parameters:

```json
[
  {
    "camera_id": "complete-example-cam",
    "status": "active",
    "stream_url": "rtsp://user:pass@192.168.1.100:554/stream",
    "parameters": {
      // Detection Settings
      "detection_classes": ["person", "car", "truck"],
      "confidence_threshold": 0.5,
      "enable_motion_detection": true,
      "enable_object_detection": true,
      "enable_anpr": false,
      "motion_threshold": 0.1,
      
      // Object Tracking Settings (NEW)
      "enable_object_tracking": true,
      "track_buffer_frames": 30,
      "min_dwell_time_seconds": 1.0,
      "tracking_confidence_threshold": 0.3,
      
      // Performance Settings
      "frame_skip": 1,
      "max_fps": 30,
      "roi_zones": [],
      
      // Event Filtering Settings
      "motion_cooldown_seconds": 2.0,
      "anpr_cooldown_seconds": 3.0
    }
  }
]
```

---

## 4. Use Case Examples

### 4.1 Entrance/Exit Tracking (People Counting)

```json
[
  {
    "camera_id": "main-entrance",
    "status": "active",
    "stream_url": "rtsp://192.168.1.101:554/stream",
    "parameters": {
      "detection_classes": ["person"],
      "confidence_threshold": 0.6,
      "enable_object_detection": true,
      "enable_object_tracking": true,
      "enable_motion_detection": false,
      "enable_anpr": false,
      "track_buffer_frames": 45,
      "min_dwell_time_seconds": 0.5,
      "tracking_confidence_threshold": 0.4,
      "frame_skip": 1,
      "max_fps": 30
    }
  }
]
```

### 4.2 Parking Lot Monitoring (Vehicles)

```json
[
  {
    "camera_id": "parking-lot-A",
    "status": "active",
    "stream_url": "rtsp://192.168.1.102:554/stream",
    "parameters": {
      "detection_classes": ["car", "truck", "bus", "motorcycle"],
      "confidence_threshold": 0.5,
      "enable_object_detection": true,
      "enable_object_tracking": true,
      "enable_motion_detection": false,
      "enable_anpr": false,
      "track_buffer_frames": 60,
      "min_dwell_time_seconds": 5.0,
      "tracking_confidence_threshold": 0.3,
      "frame_skip": 2,
      "max_fps": 15
    }
  }
]
```

### 4.3 Gate Entry with ANPR

```json
[
  {
    "camera_id": "gate-entrance",
    "status": "active",
    "stream_url": "rtsp://192.168.1.103:554/stream",
    "parameters": {
      "detection_classes": ["car", "truck", "bus"],
      "confidence_threshold": 0.5,
      "enable_object_detection": true,
      "enable_object_tracking": true,
      "enable_motion_detection": false,
      "enable_anpr": true,
      "track_buffer_frames": 30,
      "min_dwell_time_seconds": 2.0,
      "tracking_confidence_threshold": 0.3,
      "anpr_cooldown_seconds": 5.0,
      "frame_skip": 1,
      "max_fps": 20
    }
  }
]
```

### 4.4 Security Corridor (Motion + People)

```json
[
  {
    "camera_id": "corridor-sec-01",
    "status": "active",
    "stream_url": "rtsp://192.168.1.104:554/stream",
    "parameters": {
      "detection_classes": ["person", "backpack", "handbag", "suitcase"],
      "confidence_threshold": 0.6,
      "enable_object_detection": true,
      "enable_object_tracking": true,
      "enable_motion_detection": true,
      "enable_anpr": false,
      "track_buffer_frames": 30,
      "min_dwell_time_seconds": 1.0,
      "tracking_confidence_threshold": 0.4,
      "motion_threshold": 0.15,
      "motion_cooldown_seconds": 3.0,
      "frame_skip": 1,
      "max_fps": 25
    }
  }
]
```

### 4.5 Low-Resource Camera (Performance Optimized)

```json
[
  {
    "camera_id": "low-priority-cam",
    "status": "active",
    "stream_url": "rtsp://192.168.1.105:554/stream",
    "parameters": {
      "detection_classes": ["person", "car"],
      "confidence_threshold": 0.5,
      "enable_object_detection": true,
      "enable_object_tracking": true,
      "enable_motion_detection": false,
      "enable_anpr": false,
      "track_buffer_frames": 30,
      "min_dwell_time_seconds": 2.0,
      "tracking_confidence_threshold": 0.3,
      "frame_skip": 3,
      "max_fps": 10
    }
  }
]
```

### 4.6 High-Accuracy Tracking (Quality over Performance)

```json
[
  {
    "camera_id": "critical-zone-cam",
    "status": "active",
    "stream_url": "rtsp://192.168.1.106:554/stream",
    "parameters": {
      "detection_classes": ["person"],
      "confidence_threshold": 0.7,
      "enable_object_detection": true,
      "enable_object_tracking": true,
      "enable_motion_detection": false,
      "enable_anpr": false,
      "track_buffer_frames": 60,
      "min_dwell_time_seconds": 0.3,
      "tracking_confidence_threshold": 0.5,
      "frame_skip": 1,
      "max_fps": 30
    }
  }
]
```

### 4.7 Loitering Detection (Long Dwell Time)

```json
[
  {
    "camera_id": "restricted-area",
    "status": "active",
    "stream_url": "rtsp://192.168.1.107:554/stream",
    "parameters": {
      "detection_classes": ["person"],
      "confidence_threshold": 0.5,
      "enable_object_detection": true,
      "enable_object_tracking": true,
      "enable_motion_detection": false,
      "enable_anpr": false,
      "track_buffer_frames": 30,
      "min_dwell_time_seconds": 30.0,
      "tracking_confidence_threshold": 0.3,
      "frame_skip": 2,
      "max_fps": 15
    }
  }
]
```

### 4.8 Multiple Cameras Registration

```json
[
  {
    "camera_id": "entrance-floor-1",
    "status": "active",
    "stream_url": "rtsp://192.168.1.110:554/stream",
    "parameters": {
      "detection_classes": ["person"],
      "confidence_threshold": 0.5,
      "enable_object_detection": true,
      "enable_object_tracking": true,
      "enable_motion_detection": false,
      "enable_anpr": false,
      "frame_skip": 1,
      "max_fps": 30
    }
  },
  {
    "camera_id": "entrance-floor-2",
    "status": "active",
    "stream_url": "rtsp://192.168.1.111:554/stream",
    "parameters": {
      "detection_classes": ["person"],
      "confidence_threshold": 0.5,
      "enable_object_detection": true,
      "enable_object_tracking": true,
      "enable_motion_detection": false,
      "enable_anpr": false,
      "frame_skip": 1,
      "max_fps": 30
    }
  },
  {
    "camera_id": "parking-lot",
    "status": "active",
    "stream_url": "rtsp://192.168.1.112:554/stream",
    "parameters": {
      "detection_classes": ["car", "truck", "motorcycle"],
      "confidence_threshold": 0.5,
      "enable_object_detection": true,
      "enable_object_tracking": true,
      "enable_motion_detection": false,
      "enable_anpr": true,
      "anpr_cooldown_seconds": 5.0,
      "frame_skip": 2,
      "max_fps": 15
    }
  }
]
```

### 4.9 Tracking Disabled (Detection Only)

```json
[
  {
    "camera_id": "legacy-detection-cam",
    "status": "active",
    "stream_url": "rtsp://192.168.1.108:554/stream",
    "parameters": {
      "detection_classes": ["person", "car"],
      "confidence_threshold": 0.5,
      "enable_object_detection": true,
      "enable_object_tracking": false,
      "enable_motion_detection": true,
      "enable_anpr": false,
      "motion_threshold": 0.1,
      "motion_cooldown_seconds": 2.0,
      "frame_skip": 1,
      "max_fps": 30
    }
  }
]
```

**Note:** When tracking is disabled, only motion and ANPR events will be published (no detection/tracking events).

### 4.10 ROI Zones Configuration

```json
[
  {
    "camera_id": "entrance-with-roi",
    "status": "active",
    "stream_url": "rtsp://192.168.1.109:554/stream",
    "parameters": {
      "detection_classes": ["person"],
      "confidence_threshold": 0.5,
      "enable_object_detection": true,
      "enable_object_tracking": true,
      "enable_motion_detection": false,
      "enable_anpr": false,
      "roi_zones": [
        {
          "name": "entrance_zone",
          "points": [
            [0.2, 0.3],
            [0.8, 0.3],
            [0.8, 0.9],
            [0.2, 0.9]
          ]
        },
        {
          "name": "exit_zone",
          "points": [
            [0.1, 0.1],
            [0.4, 0.1],
            [0.4, 0.5],
            [0.1, 0.5]
          ]
        }
      ],
      "track_buffer_frames": 30,
      "min_dwell_time_seconds": 1.0,
      "frame_skip": 1,
      "max_fps": 30
    }
  }
]
```

---

## Parameter Specifications

### Required Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `camera_id` | string | ✅ Yes | Unique identifier for camera |
| `stream_url` | string | ✅ Yes | RTSP/RTMP/HTTP stream URL |

### Optional Root Fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `status` | string | "active" | Camera status: "active", "inactive", or "error" |
| `parameters` | object | {} | Camera processing parameters (see below) |

### Detection Settings Parameters

| Parameter | Type | Default | Range/Options | Description |
|-----------|------|---------|---------------|-------------|
| `detection_classes` | array[string] | `["person", "car", "truck"]` | See [Detection Classes](#detection-classes) | YOLO classes to detect |
| `confidence_threshold` | float | 0.5 | 0.0 - 1.0 | Minimum confidence for detection |
| `enable_object_detection` | boolean | true | true/false | Enable/disable object detection |
| `enable_motion_detection` | boolean | true | true/false | Enable/disable motion detection |
| `enable_anpr` | boolean | false | true/false | Enable/disable license plate recognition |
| `motion_threshold` | float | 0.1 | 0.0 - 1.0 | Motion sensitivity (lower = more sensitive) |

### Object Tracking Settings (NEW)

| Parameter | Type | Default | Range | Description |
|-----------|------|---------|-------|-------------|
| `enable_object_tracking` | boolean | true | true/false | Enable/disable ByteTrack tracking |
| `track_buffer_frames` | integer | 30 | 1 - 300 | Frames to wait before "left" event (30 frames ≈ 1s at 30 FPS) |
| `min_dwell_time_seconds` | float | 1.0 | 0.0 - 3600.0 | Minimum dwell time to trigger "left" event |
| `tracking_confidence_threshold` | float | 0.3 | 0.0 - 1.0 | Confidence threshold for tracking (lower than detection) |

### Performance Settings

| Parameter | Type | Default | Range | Description |
|-----------|------|---------|-------|-------------|
| `frame_skip` | integer | 1 | 1 - 10 | Process every Nth frame (1 = every frame, 2 = every other frame) |
| `max_fps` | integer | 30 | 1 - 60 | Maximum frames per second to process |
| `roi_zones` | array[object] | [] | See [ROI Format](#roi-zones-format) | Regions of Interest (future use) |

### Event Filtering Settings

| Parameter | Type | Default | Range | Description |
|-----------|------|---------|-------|-------------|
| `motion_cooldown_seconds` | float | 2.0 | 0.0 - 60.0 | Minimum seconds between motion events |
| `anpr_cooldown_seconds` | float | 3.0 | 0.0 - 60.0 | Minimum seconds between ANPR events per plate |

---

## Detection Classes

Available YOLO COCO detection classes:

### Common Classes

```json
"detection_classes": [
  "person",
  "bicycle",
  "car",
  "motorcycle",
  "bus",
  "truck",
  "traffic light",
  "stop sign",
  "dog",
  "cat",
  "backpack",
  "handbag",
  "suitcase",
  "umbrella",
  "bottle",
  "cup",
  "chair",
  "couch",
  "potted plant",
  "bed",
  "dining table",
  "laptop",
  "mouse",
  "keyboard",
  "cell phone",
  "book"
]
```

### All Available Classes (80 total)

```
person, bicycle, car, motorcycle, airplane, bus, train, truck, boat,
traffic light, fire hydrant, stop sign, parking meter, bench, bird, cat,
dog, horse, sheep, cow, elephant, bear, zebra, giraffe, backpack, umbrella,
handbag, tie, suitcase, frisbee, skis, snowboard, sports ball, kite,
baseball bat, baseball glove, skateboard, surfboard, tennis racket, bottle,
wine glass, cup, fork, knife, spoon, bowl, banana, apple, sandwich, orange,
broccoli, carrot, hot dog, pizza, donut, cake, chair, couch, potted plant,
bed, dining table, toilet, tv, laptop, mouse, remote, keyboard, cell phone,
microwave, oven, toaster, sink, refrigerator, book, clock, vase, scissors,
teddy bear, hair drier, toothbrush
```

---

## ROI Zones Format

```json
"roi_zones": [
  {
    "name": "zone_name",
    "points": [
      [x1, y1],
      [x2, y2],
      [x3, y3],
      [x4, y4]
    ]
  }
]
```

- **Coordinates:** Normalized (0.0 - 1.0) relative to frame dimensions
- **Points:** Array of [x, y] coordinates defining polygon
- **Minimum:** 3 points (triangle)
- **Order:** Counter-clockwise or clockwise

---

## Stream URL Formats

### RTSP (Most Common)

```json
"stream_url": "rtsp://username:password@192.168.1.100:554/stream1"
"stream_url": "rtsp://192.168.1.100:554/media/video1"
"stream_url": "rtsp://admin:admin123@camera.local:554/h264"
```

### RTMP

```json
"stream_url": "rtmp://192.168.1.100:1935/live/stream"
```

### HTTP/HTTPS

```json
"stream_url": "http://192.168.1.100:8080/video.mjpg"
"stream_url": "https://camera.example.com/stream"
```

### File (for testing)

```json
"stream_url": "/path/to/video.mp4"
"stream_url": "file:///path/to/video.mp4"
```

---

## Validation Rules

### Camera ID
- **Required:** Yes
- **Type:** String
- **Pattern:** `^[a-zA-Z0-9_-]+$`
- **Length:** 1-255 characters
- **Unique:** Must be unique across all cameras

### Stream URL
- **Required:** Yes
- **Type:** String (valid URL)
- **Protocols:** rtsp, rtmp, http, https, file
- **Length:** 1-2048 characters

### Numeric Ranges

```python
# Confidence and thresholds
0.0 <= confidence_threshold <= 1.0
0.0 <= tracking_confidence_threshold <= 1.0
0.0 <= motion_threshold <= 1.0

# Frame processing
1 <= frame_skip <= 10
1 <= max_fps <= 60
1 <= track_buffer_frames <= 300

# Time values
0.0 <= min_dwell_time_seconds <= 3600.0
0.0 <= motion_cooldown_seconds <= 60.0
0.0 <= anpr_cooldown_seconds <= 60.0
```

### Arrays
- `detection_classes`: Minimum 1 class, maximum 80 classes
- `roi_zones`: Maximum 10 zones per camera

---

## Response Examples

### Success Response (201 Created)

```json
{
  "message": "Successfully added 1 camera(s)",
  "cameras": [
    {
      "camera_id": "entrance-cam-01",
      "status": "active",
      "stream_url": "rtsp://192.168.1.100:554/stream",
      "parameters": {
        "detection_classes": ["person"],
        "confidence_threshold": 0.5,
        "enable_motion_detection": true,
        "enable_object_detection": true,
        "enable_object_tracking": true,
        "enable_anpr": false,
        "frame_skip": 1,
        "max_fps": 30,
        "track_buffer_frames": 30,
        "min_dwell_time_seconds": 1.0,
        "tracking_confidence_threshold": 0.3,
        "motion_threshold": 0.1,
        "motion_cooldown_seconds": 2.0,
        "anpr_cooldown_seconds": 3.0,
        "roi_zones": []
      }
    }
  ]
}
```

### Error Response (400 Bad Request)

```json
{
  "detail": "Camera entrance-cam-01 already exists"
}
```

```json
{
  "detail": [
    {
      "loc": ["body", 0, "camera_id"],
      "msg": "field required",
      "type": "value_error.missing"
    }
  ]
}
```

```json
{
  "detail": [
    {
      "loc": ["body", 0, "parameters", "confidence_threshold"],
      "msg": "ensure this value is less than or equal to 1.0",
      "type": "value_error.number.not_le"
    }
  ]
}
```

---

## Backend Validation Example

### Python (FastAPI/Pydantic)

```python
from pydantic import BaseModel, Field, validator
from typing import List, Optional
from enum import Enum

class CameraStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    ERROR = "error"

class ROIZone(BaseModel):
    name: str
    points: List[List[float]]  # [[x, y], ...]
    
    @validator('points')
    def validate_points(cls, v):
        if len(v) < 3:
            raise ValueError('ROI zone must have at least 3 points')
        for point in v:
            if len(point) != 2:
                raise ValueError('Each point must have exactly 2 coordinates [x, y]')
            if not (0.0 <= point[0] <= 1.0 and 0.0 <= point[1] <= 1.0):
                raise ValueError('Coordinates must be normalized (0.0-1.0)')
        return v

class CameraParameters(BaseModel):
    # Detection settings
    detection_classes: List[str] = Field(
        default_factory=lambda: ["person", "car", "truck"]
    )
    confidence_threshold: float = Field(default=0.5, ge=0.0, le=1.0)
    enable_motion_detection: bool = True
    enable_object_detection: bool = True
    enable_anpr: bool = False
    motion_threshold: float = Field(default=0.1, ge=0.0, le=1.0)
    
    # Tracking settings
    enable_object_tracking: bool = True
    track_buffer_frames: int = Field(default=30, ge=1, le=300)
    min_dwell_time_seconds: float = Field(default=1.0, ge=0.0, le=3600.0)
    tracking_confidence_threshold: float = Field(default=0.3, ge=0.0, le=1.0)
    
    # Performance settings
    frame_skip: int = Field(default=1, ge=1, le=10)
    max_fps: int = Field(default=30, ge=1, le=60)
    roi_zones: List[ROIZone] = Field(default_factory=list)
    
    # Filtering settings
    motion_cooldown_seconds: float = Field(default=2.0, ge=0.0, le=60.0)
    anpr_cooldown_seconds: float = Field(default=3.0, ge=0.0, le=60.0)
    
    @validator('detection_classes')
    def validate_classes(cls, v):
        if not v or len(v) == 0:
            raise ValueError('At least one detection class required')
        if len(v) > 80:
            raise ValueError('Maximum 80 detection classes allowed')
        return v
    
    @validator('roi_zones')
    def validate_zones(cls, v):
        if len(v) > 10:
            raise ValueError('Maximum 10 ROI zones allowed')
        return v

class CameraConfig(BaseModel):
    camera_id: str = Field(..., min_length=1, max_length=255)
    status: CameraStatus = CameraStatus.ACTIVE
    stream_url: str = Field(..., min_length=1, max_length=2048)
    parameters: CameraParameters = Field(default_factory=CameraParameters)
    
    @validator('camera_id')
    def validate_camera_id(cls, v):
        import re
        if not re.match(r'^[a-zA-Z0-9_-]+$', v):
            raise ValueError('Camera ID can only contain letters, numbers, underscores, and hyphens')
        return v
    
    @validator('stream_url')
    def validate_stream_url(cls, v):
        if not any(v.startswith(proto) for proto in ['rtsp://', 'rtmp://', 'http://', 'https://', 'file://', '/']):
            raise ValueError('Invalid stream URL protocol')
        return v
```

### TypeScript Example

```typescript
interface ROIZone {
  name: string;
  points: [number, number][];  // Array of [x, y] tuples
}

interface CameraParameters {
  // Detection settings
  detection_classes?: string[];
  confidence_threshold?: number;
  enable_motion_detection?: boolean;
  enable_object_detection?: boolean;
  enable_anpr?: boolean;
  motion_threshold?: number;
  
  // Tracking settings
  enable_object_tracking?: boolean;
  track_buffer_frames?: number;
  min_dwell_time_seconds?: number;
  tracking_confidence_threshold?: number;
  
  // Performance settings
  frame_skip?: number;
  max_fps?: number;
  roi_zones?: ROIZone[];
  
  // Filtering settings
  motion_cooldown_seconds?: number;
  anpr_cooldown_seconds?: number;
}

interface CameraConfig {
  camera_id: string;
  status?: "active" | "inactive" | "error";
  stream_url: string;
  parameters?: CameraParameters;
}

// Validation function
function validateCameraConfig(config: CameraConfig): string[] {
  const errors: string[] = [];
  
  // Validate camera_id
  if (!config.camera_id || config.camera_id.length === 0) {
    errors.push("camera_id is required");
  } else if (!/^[a-zA-Z0-9_-]+$/.test(config.camera_id)) {
    errors.push("camera_id can only contain letters, numbers, underscores, and hyphens");
  }
  
  // Validate stream_url
  if (!config.stream_url || config.stream_url.length === 0) {
    errors.push("stream_url is required");
  } else if (!config.stream_url.match(/^(rtsp|rtmp|https?|file):\/\/.+/)) {
    errors.push("Invalid stream_url protocol");
  }
  
  // Validate parameters if provided
  if (config.parameters) {
    const p = config.parameters;
    
    if (p.confidence_threshold !== undefined && (p.confidence_threshold < 0 || p.confidence_threshold > 1)) {
      errors.push("confidence_threshold must be between 0.0 and 1.0");
    }
    
    if (p.tracking_confidence_threshold !== undefined && (p.tracking_confidence_threshold < 0 || p.tracking_confidence_threshold > 1)) {
      errors.push("tracking_confidence_threshold must be between 0.0 and 1.0");
    }
    
    if (p.frame_skip !== undefined && (p.frame_skip < 1 || p.frame_skip > 10)) {
      errors.push("frame_skip must be between 1 and 10");
    }
    
    if (p.max_fps !== undefined && (p.max_fps < 1 || p.max_fps > 60)) {
      errors.push("max_fps must be between 1 and 60");
    }
    
    if (p.track_buffer_frames !== undefined && (p.track_buffer_frames < 1 || p.track_buffer_frames > 300)) {
      errors.push("track_buffer_frames must be between 1 and 300");
    }
    
    if (p.detection_classes && p.detection_classes.length === 0) {
      errors.push("At least one detection class required");
    }
  }
  
  return errors;
}
```

---

## Testing Your API Integration

### Test Cases

1. **Minimal payload** - Only required fields
2. **Complete payload** - All parameters specified
3. **Invalid camera_id** - Special characters, empty string
4. **Invalid stream_url** - Bad protocol, empty string
5. **Out of range values** - confidence > 1.0, negative values
6. **Invalid detection classes** - Empty array, unknown classes
7. **Multiple cameras** - Array with 2+ cameras
8. **Duplicate camera_id** - Attempt to add same camera twice
9. **ROI validation** - Invalid coordinates, too few points

---

## Performance Guidelines

### Recommended Settings by Use Case

| Use Case | frame_skip | max_fps | track_buffer_frames | Notes |
|----------|------------|---------|---------------------|-------|
| High-traffic entrance | 1 | 30 | 30 | Maximum accuracy |
| Parking lot | 2 | 15 | 60 | Balanced performance |
| Perimeter security | 2 | 20 | 45 | Motion + tracking |
| Low-priority area | 3 | 10 | 30 | Resource saving |
| Critical zone | 1 | 30 | 60 | High accuracy |

### CPU Impact Estimation

```
CPU usage per camera ≈ Base + (FPS × Complexity)

Where:
- Base: ~10% per camera
- FPS impact: ~0.5% per FPS
- Complexity factors:
  - Detection enabled: +1.0x
  - Tracking enabled: +0.1x
  - Motion enabled: +0.2x
  - ANPR enabled: +0.5x
  
Example:
30 FPS, all features = 10% + (30 × 0.5%) × (1.0 + 0.1 + 0.2 + 0.5) = ~37% CPU per camera
```

---

## Troubleshooting

### Common Issues

**Issue:** Camera not connecting
- Check stream_url is accessible
- Verify credentials in URL
- Test with VLC or ffplay first

**Issue:** No tracking events
- Ensure `enable_object_tracking: true`
- Lower `min_dwell_time_seconds`
- Check `detection_classes` includes expected objects

**Issue:** Too many events
- Increase `min_dwell_time_seconds`
- Increase `track_buffer_frames`
- Adjust `confidence_threshold`

**Issue:** High CPU usage
- Increase `frame_skip`
- Reduce `max_fps`
- Disable unused features (motion, ANPR)

---

## Support

For API questions:
- API documentation: `GET /docs` (Swagger UI)
- Health check: `GET /api/health`
- List cameras: `GET /api/cameras`
- Review [EVENT_TYPES_REFERENCE.md](EVENT_TYPES_REFERENCE.md) for event formats

---

**Last Updated:** October 9, 2025  
**API Version:** 2.0 (with ByteTrack tracking)

