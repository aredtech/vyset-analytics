# API Request & Response Documentation

## Overview

This document provides comprehensive request and response examples for the VMS Analytics API. The API is built with FastAPI and provides endpoints for camera management and health monitoring.

**Base URL:** `http://localhost:8000`

---

## Table of Contents

- [Authentication](#authentication)
- [Common Response Codes](#common-response-codes)
- [Endpoints](#endpoints)
  - [Register Cameras](#1-register-cameras)
  - [List All Cameras](#2-list-all-cameras)
  - [Get Camera by ID](#3-get-camera-by-id)
  - [Delete Camera](#4-delete-camera)
  - [Health Check](#5-health-check)
- [Data Models](#data-models)
- [Error Responses](#error-responses)
- [Examples](#examples)

---

## Authentication

Currently, the API does not require authentication. This may be added in future versions.

---

## Common Response Codes

| Status Code | Description |
|-------------|-------------|
| 200 | OK - Request successful |
| 201 | Created - Resource created successfully |
| 400 | Bad Request - Invalid input data |
| 404 | Not Found - Resource not found |
| 422 | Unprocessable Entity - Validation error |
| 500 | Internal Server Error - Server error |

---

## Endpoints

### 1. Register Cameras

Register and start processing one or more camera streams.

**Endpoint:** `POST /api/cameras`

**Request Headers:**
```http
Content-Type: application/json
```

#### Request Body (Single Camera)

```json
[
  {
    "camera_id": "camera_001",
    "status": "active",
    "stream_url": "rtsp://admin:password@192.168.1.100:554/stream1",
    "parameters": {
      "detection_classes": ["person", "car", "truck"],
      "confidence_threshold": 0.5,
      "roi_zones": [
        {
          "name": "entrance",
          "points": [[0.1, 0.1], [0.9, 0.1], [0.9, 0.9], [0.1, 0.9]]
        }
      ],
      "enable_motion_detection": true,
      "enable_object_detection": true,
      "enable_anpr": false,
      "motion_threshold": 0.1,
      "frame_skip": 1,
      "max_fps": 30,
      "enable_object_tracking": true,
      "track_buffer_frames": 30,
      "min_dwell_time_seconds": 1.0,
      "tracking_confidence_threshold": 0.3,
      "motion_cooldown_seconds": 2.0,
      "anpr_cooldown_seconds": 3.0
    }
  }
]
```

#### Request Body (Multiple Cameras)

```json
[
  {
    "camera_id": "entrance_cam",
    "stream_url": "rtsp://admin:pass@192.168.1.100:554/stream",
    "status": "active",
    "parameters": {
      "detection_classes": ["person"],
      "confidence_threshold": 0.6,
      "enable_object_tracking": true,
      "enable_motion_detection": true
    }
  },
  {
    "camera_id": "parking_cam",
    "stream_url": "rtsp://admin:pass@192.168.1.101:554/stream",
    "status": "active",
    "parameters": {
      "detection_classes": ["car", "truck"],
      "enable_anpr": true,
      "anpr_cooldown_seconds": 5.0
    }
  }
]
```

#### Minimal Request (Using Defaults)

```json
[
  {
    "camera_id": "simple_cam",
    "stream_url": "rtsp://192.168.1.100:554/stream"
  }
]
```

#### Success Response (201 Created)

```json
{
  "message": "Processed 2 camera(s)",
  "results": {
    "success": ["entrance_cam", "parking_cam"],
    "failed": []
  }
}
```

#### Partial Success Response (201 Created)

```json
{
  "message": "Processed 2 camera(s)",
  "results": {
    "success": ["entrance_cam"],
    "failed": [
      {
        "camera_id": "parking_cam",
        "reason": "Camera already exists or failed to start"
      }
    ]
  }
}
```

#### Validation Error Response (422)

```json
{
  "detail": [
    {
      "loc": ["body", 0, "stream_url"],
      "msg": "field required",
      "type": "value_error.missing"
    }
  ]
}
```

---

### 2. List All Cameras

Get a list of all active cameras and their configurations.

**Endpoint:** `GET /api/cameras`

**Request Headers:** None required

#### Success Response (200 OK)

```json
{
  "cameras": [
    {
      "camera_id": "camera_001",
      "status": "active",
      "stream_url": "rtsp://admin:password@192.168.1.100:554/stream1",
      "parameters": {
        "detection_classes": ["person", "car", "truck"],
        "confidence_threshold": 0.5,
        "roi_zones": [
          {
            "name": "entrance",
            "points": [[0.1, 0.1], [0.9, 0.1], [0.9, 0.9], [0.1, 0.9]]
          }
        ],
        "enable_motion_detection": true,
        "enable_object_detection": true,
        "enable_anpr": false,
        "motion_threshold": 0.1,
        "frame_skip": 1,
        "max_fps": 30,
        "enable_object_tracking": true,
        "track_buffer_frames": 30,
        "min_dwell_time_seconds": 1.0,
        "tracking_confidence_threshold": 0.3,
        "motion_cooldown_seconds": 2.0,
        "anpr_cooldown_seconds": 3.0
      }
    },
    {
      "camera_id": "parking_cam",
      "status": "active",
      "stream_url": "rtsp://admin:pass@192.168.1.101:554/stream",
      "parameters": {
        "detection_classes": ["car", "truck"],
        "confidence_threshold": 0.5,
        "roi_zones": [],
        "enable_motion_detection": true,
        "enable_object_detection": true,
        "enable_anpr": true,
        "motion_threshold": 0.1,
        "frame_skip": 1,
        "max_fps": 30,
        "enable_object_tracking": true,
        "track_buffer_frames": 30,
        "min_dwell_time_seconds": 1.0,
        "tracking_confidence_threshold": 0.3,
        "motion_cooldown_seconds": 2.0,
        "anpr_cooldown_seconds": 5.0
      }
    }
  ],
  "count": 2
}
```

#### Empty Response (200 OK)

```json
{
  "cameras": [],
  "count": 0
}
```

---

### 3. Get Camera by ID

Get configuration details for a specific camera.

**Endpoint:** `GET /api/cameras/{camera_id}`

**Path Parameters:**
- `camera_id` (string, required): Camera identifier

#### Example Request

```
GET /api/cameras/camera_001
```

#### Success Response (200 OK)

```json
{
  "camera_id": "camera_001",
  "status": "active",
  "stream_url": "rtsp://admin:password@192.168.1.100:554/stream1",
  "parameters": {
    "detection_classes": ["person", "car", "truck"],
    "confidence_threshold": 0.5,
    "roi_zones": [
      {
        "name": "entrance",
        "points": [[0.1, 0.1], [0.9, 0.1], [0.9, 0.9], [0.1, 0.9]]
      }
    ],
    "enable_motion_detection": true,
    "enable_object_detection": true,
    "enable_anpr": false,
    "motion_threshold": 0.1,
    "frame_skip": 1,
    "max_fps": 30,
    "enable_object_tracking": true,
    "track_buffer_frames": 30,
    "min_dwell_time_seconds": 1.0,
    "tracking_confidence_threshold": 0.3,
    "motion_cooldown_seconds": 2.0,
    "anpr_cooldown_seconds": 3.0
  }
}
```

#### Not Found Response (404)

```json
{
  "detail": "Camera camera_001 not found"
}
```

---

### 4. Delete Camera

Stop processing and remove a camera from the system.

**Endpoint:** `DELETE /api/cameras/{camera_id}`

**Path Parameters:**
- `camera_id` (string, required): Camera identifier

#### Example Request

```
DELETE /api/cameras/camera_001
```

#### Success Response (200 OK)

```json
{
  "message": "Camera camera_001 stopped and removed successfully"
}
```

#### Not Found Response (404)

```json
{
  "detail": "Camera camera_001 not found"
}
```

---

### 5. Health Check

Check the health status of the Analytics service.

**Endpoint:** `GET /api/health`

**Request Headers:** None required

#### Healthy Response (200 OK)

```json
{
  "status": "healthy",
  "redis_connected": true,
  "active_cameras": 2
}
```

#### Degraded Response (200 OK)

```json
{
  "status": "degraded",
  "redis_connected": false,
  "active_cameras": 2
}
```

---

## Data Models

### CameraConfig

Main camera configuration model.

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| camera_id | string | Yes | - | Unique camera identifier |
| status | string | No | "active" | Camera status: "active", "inactive", "error" |
| stream_url | string | Yes | - | RTSP/HTTP stream URL |
| parameters | CameraParameters | No | {} | Processing parameters |

### CameraParameters

Camera processing parameters.

| Field | Type | Required | Default | Range | Description |
|-------|------|----------|---------|-------|-------------|
| detection_classes | array[string] | No | ["person", "car", "truck"] | - | Object classes to detect |
| confidence_threshold | float | No | 0.5 | 0.0-1.0 | Detection confidence threshold |
| roi_zones | array[ROIZone] | No | [] | - | Region of Interest zones |
| enable_motion_detection | boolean | No | true | - | Enable motion detection |
| enable_object_detection | boolean | No | true | - | Enable object detection |
| enable_anpr | boolean | No | false | - | Enable license plate recognition |
| motion_threshold | float | No | 0.1 | 0.0-1.0 | Motion detection sensitivity |
| frame_skip | integer | No | 1 | ≥1 | Process every Nth frame |
| max_fps | integer | No | 30 | ≥1 | Maximum frames per second |
| enable_object_tracking | boolean | No | true | - | Enable object tracking (ByteTrack) |
| track_buffer_frames | integer | No | 30 | ≥1 | Frames before object considered 'left' |
| min_dwell_time_seconds | float | No | 1.0 | ≥0.0 | Min time before 'left' event |
| tracking_confidence_threshold | float | No | 0.3 | 0.0-1.0 | Tracking confidence threshold |
| motion_cooldown_seconds | float | No | 2.0 | ≥0.0 | Cooldown between motion events |
| anpr_cooldown_seconds | float | No | 3.0 | ≥0.0 | Cooldown between ANPR events |

### ROIZone

Region of Interest zone definition.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| name | string | Yes | Zone name |
| points | array[array[float]] | Yes | Polygon vertices as [x, y] coordinates (0.0-1.0, normalized) |

### CameraListResponse

Response model for listing cameras.

| Field | Type | Description |
|-------|------|-------------|
| cameras | array[CameraConfig] | List of camera configurations |
| count | integer | Total number of cameras |

### HealthResponse

Health check response model.

| Field | Type | Description |
|-------|------|-------------|
| status | string | Service status: "healthy" or "degraded" |
| redis_connected | boolean | Redis connection status |
| active_cameras | integer | Number of active cameras |

---

## Error Responses

### 400 Bad Request

Returned when the request is malformed or contains invalid data.

```json
{
  "detail": "Invalid request format"
}
```

### 404 Not Found

Returned when the requested resource doesn't exist.

```json
{
  "detail": "Camera camera_xyz not found"
}
```

### 422 Unprocessable Entity

Returned when validation fails.

```json
{
  "detail": [
    {
      "loc": ["body", 0, "parameters", "confidence_threshold"],
      "msg": "ensure this value is less than or equal to 1.0",
      "type": "value_error.number.not_le",
      "ctx": {
        "limit_value": 1.0
      }
    }
  ]
}
```

### 500 Internal Server Error

Returned when an unexpected server error occurs.

```json
{
  "detail": "Internal server error"
}
```

---

## Examples

### Example 1: Simple Camera Registration

Register a camera with minimal configuration (using defaults).

**Request:**
```bash
curl -X POST "http://localhost:8000/api/cameras" \
  -H "Content-Type: application/json" \
  -d '[
    {
      "camera_id": "lobby_cam",
      "stream_url": "rtsp://192.168.1.50:554/stream"
    }
  ]'
```

**Response:**
```json
{
  "message": "Processed 1 camera(s)",
  "results": {
    "success": ["lobby_cam"],
    "failed": []
  }
}
```

### Example 2: Advanced Camera with ROI

Register a camera with custom detection zones.

**Request:**
```bash
curl -X POST "http://localhost:8000/api/cameras" \
  -H "Content-Type: application/json" \
  -d '[
    {
      "camera_id": "entrance_main",
      "stream_url": "rtsp://admin:pass@192.168.1.100:554/main",
      "parameters": {
        "detection_classes": ["person"],
        "confidence_threshold": 0.7,
        "roi_zones": [
          {
            "name": "entrance_area",
            "points": [[0.2, 0.3], [0.8, 0.3], [0.8, 0.8], [0.2, 0.8]]
          }
        ],
        "enable_object_tracking": true,
        "min_dwell_time_seconds": 2.0
      }
    }
  ]'
```

**Response:**
```json
{
  "message": "Processed 1 camera(s)",
  "results": {
    "success": ["entrance_main"],
    "failed": []
  }
}
```

### Example 3: ANPR Camera

Register a camera configured for license plate recognition.

**Request:**
```bash
curl -X POST "http://localhost:8000/api/cameras" \
  -H "Content-Type: application/json" \
  -d '[
    {
      "camera_id": "parking_entrance",
      "stream_url": "rtsp://admin:pass@192.168.1.101:554/stream",
      "parameters": {
        "detection_classes": ["car", "truck"],
        "enable_anpr": true,
        "anpr_cooldown_seconds": 5.0,
        "enable_object_tracking": true
      }
    }
  ]'
```

**Response:**
```json
{
  "message": "Processed 1 camera(s)",
  "results": {
    "success": ["parking_entrance"],
    "failed": []
  }
}
```

### Example 4: List All Cameras

**Request:**
```bash
curl -X GET "http://localhost:8000/api/cameras"
```

**Response:**
```json
{
  "cameras": [
    {
      "camera_id": "lobby_cam",
      "status": "active",
      "stream_url": "rtsp://192.168.1.50:554/stream",
      "parameters": {
        "detection_classes": ["person", "car", "truck"],
        "confidence_threshold": 0.5,
        "roi_zones": [],
        "enable_motion_detection": true,
        "enable_object_detection": true,
        "enable_anpr": false,
        "motion_threshold": 0.1,
        "frame_skip": 1,
        "max_fps": 30,
        "enable_object_tracking": true,
        "track_buffer_frames": 30,
        "min_dwell_time_seconds": 1.0,
        "tracking_confidence_threshold": 0.3,
        "motion_cooldown_seconds": 2.0,
        "anpr_cooldown_seconds": 3.0
      }
    }
  ],
  "count": 1
}
```

### Example 5: Get Specific Camera

**Request:**
```bash
curl -X GET "http://localhost:8000/api/cameras/lobby_cam"
```

**Response:**
```json
{
  "camera_id": "lobby_cam",
  "status": "active",
  "stream_url": "rtsp://192.168.1.50:554/stream",
  "parameters": {
    "detection_classes": ["person", "car", "truck"],
    "confidence_threshold": 0.5,
    "roi_zones": [],
    "enable_motion_detection": true,
    "enable_object_detection": true,
    "enable_anpr": false,
    "motion_threshold": 0.1,
    "frame_skip": 1,
    "max_fps": 30,
    "enable_object_tracking": true,
    "track_buffer_frames": 30,
    "min_dwell_time_seconds": 1.0,
    "tracking_confidence_threshold": 0.3,
    "motion_cooldown_seconds": 2.0,
    "anpr_cooldown_seconds": 3.0
  }
}
```

### Example 6: Delete Camera

**Request:**
```bash
curl -X DELETE "http://localhost:8000/api/cameras/lobby_cam"
```

**Response:**
```json
{
  "message": "Camera lobby_cam stopped and removed successfully"
}
```

### Example 7: Health Check

**Request:**
```bash
curl -X GET "http://localhost:8000/api/health"
```

**Response:**
```json
{
  "status": "healthy",
  "redis_connected": true,
  "active_cameras": 3
}
```

### Example 8: Bulk Camera Registration

Register multiple cameras with different configurations.

**Request:**
```bash
curl -X POST "http://localhost:8000/api/cameras" \
  -H "Content-Type: application/json" \
  -d '[
    {
      "camera_id": "entrance_1",
      "stream_url": "rtsp://192.168.1.100:554/stream",
      "parameters": {
        "detection_classes": ["person"],
        "confidence_threshold": 0.6
      }
    },
    {
      "camera_id": "entrance_2",
      "stream_url": "rtsp://192.168.1.101:554/stream",
      "parameters": {
        "detection_classes": ["person"],
        "confidence_threshold": 0.6
      }
    },
    {
      "camera_id": "parking_lot",
      "stream_url": "rtsp://192.168.1.102:554/stream",
      "parameters": {
        "detection_classes": ["car", "truck"],
        "enable_anpr": true
      }
    }
  ]'
```

**Response:**
```json
{
  "message": "Processed 3 camera(s)",
  "results": {
    "success": ["entrance_1", "entrance_2", "parking_lot"],
    "failed": []
  }
}
```

---

## Notes

1. **Stream URLs**: The API supports RTSP streams. Ensure your stream URLs are accessible from the Analytics service.

2. **ROI Zones**: Coordinates are normalized (0.0 to 1.0) where:
   - (0.0, 0.0) = top-left corner
   - (1.0, 1.0) = bottom-right corner

3. **Default Parameters**: When not specified, cameras use default parameters. Only override what you need to customize.

4. **Event Filtering**: The system automatically filters events based on cooldown periods to prevent duplicate events.

5. **Object Tracking**: When enabled, the system assigns unique track IDs to objects and tracks them across frames.

6. **Status Monitoring**: Use the health endpoint to monitor service status and active camera count.

7. **Error Handling**: All endpoints return appropriate HTTP status codes and descriptive error messages.

---

## Testing with Postman

1. Import the `Analytics_API.postman_collection.json` file into Postman
2. Set the `base_url` variable to your server address (default: `http://localhost:8000`)
3. Use the provided examples to test each endpoint
4. View response examples in the collection

---

## Related Documentation

- [Event Filtering Documentation](./EVENT_FILTERING.md)
- [Event Types Reference](./EVENT_TYPES_REFERENCE.md)
- [API Payload Reference](./API_PAYLOAD_REFERENCE.md)
- [Implementation Guide](./IMPLEMENTATION_COMPLETE.md)

---

**Last Updated:** October 2025
**API Version:** 2.0

