# Video Analytics Service

A standalone video analytics service for real-time object detection, motion detection, ANPR (Automatic Number Plate Recognition), and garbage detection with event tracking, snapshot management, and retention policies.

## 🚀 Features

### Core Analytics
- **Object Detection**: YOLOv8-based detection for persons, cars, trucks, and custom classes
- **Object Tracking**: ByteTrack algorithm for tracking objects across frames with lifecycle events (entered/updated/left)
- **Motion Detection**: Frame differencing with background subtraction for motion detection
- **ANPR**: License plate recognition using EasyOCR
- **Garbage Detection**: Custom-trained YOLO model for garbage detection with optional tracking

### Event Management
- **Event Filtering**: Cooldown periods and deduplication to prevent event flooding
- **Snapshot Management**: Automatic snapshot capture with bounding box annotations
- **Event Retention**: Configurable retention policies per camera with automatic cleanup
- **Real-time Publishing**: Redis Pub/Sub for real-time event streaming

### API & Integration
- **RESTful API**: FastAPI-based endpoints for camera and event management
- **Database Storage**: PostgreSQL for persistent event storage
- **Health Monitoring**: Health check endpoints and status reporting

## 📋 Table of Contents

- [Quick Start](#quick-start)
- [Architecture](#architecture)
- [Configuration](#configuration)
- [API Documentation](#api-documentation)
- [Development](#development)
- [Deployment](#deployment)
- [Project Structure](#project-structure)
- [Documentation](#documentation)

## Quick Start

### Prerequisites

- Docker and Docker Compose
- PostgreSQL database (or use Docker Compose)
- Redis server (or use Docker Compose)
- Python 3.11+ (for local development)

### Using Docker Compose

1. **Clone the repository**:
   ```bash
   git clone <repository-url>
   cd analytics_v2
   ```

2. **Configure environment**:
   ```bash
   cp .env.example .env
   # Edit .env with your database and Redis configuration
   ```

3. **Start the service**:
   ```bash
   docker compose up -d
   ```

4. **Verify the service**:
   ```bash
   curl http://localhost:8069/
   # Should return: {"service": "Video Analytics Service", "version": "1.0.0", "status": "running"}
   ```

### Register a Camera

```bash
curl -X POST http://localhost:8069/api/cameras \
  -H "Content-Type: application/json" \
  -d '{
    "camera_id": "camera_001",
    "camera_name": "Main Entrance",
    "stream_url": "rtsp://your-camera-stream-url",
    "parameters": {
      "enable_object_detection": true,
      "enable_motion_detection": true,
      "detection_classes": ["person", "car"],
      "confidence_threshold": 0.5
    }
  }'
```

### Check Health

```bash
curl http://localhost:8069/api/health
```

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    FastAPI Application                       │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐    │
│  │ Camera API   │  │  Events API  │  │ Health Check  │    │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘    │
└─────────┼──────────────────┼──────────────────┼──────────┘
          │                  │                  │
          ▼                  ▼                  ▼
┌─────────────────────────────────────────────────────────────┐
│              Video Worker & Camera Manager                   │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐    │
│  │ Detection    │  │ Motion       │  │ ANPR         │    │
│  │ + Tracking   │  │ Detection    │  │ Detection    │    │
│  └──────────────┘  └──────────────┘  └──────────────┘    │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐    │
│  │ Garbage      │  │ Event        │  │ Snapshot     │    │
│  │ Detection    │  │ Filter       │  │ Manager      │    │
│  └──────────────┘  └──────────────┘  └──────────────┘    │
└─────────┬──────────────────┬──────────────────┬──────────┘
          │                  │                  │
          ▼                  ▼                  ▼
┌─────────────────┐  ┌──────────────┐  ┌──────────────┐
│   PostgreSQL     │  │    Redis     │  │  Snapshots   │
│   (Events DB)    │  │  (Pub/Sub)   │  │  (Files)     │
└─────────────────┘  └──────────────┘  └──────────────┘
```

## Configuration

### Environment Variables

Create a `.env` file based on `.env.example`:

```bash
# Redis Configuration
REDIS_HOST=redis
REDIS_PORT=6379
REDIS_DB=0
REDIS_CHANNEL_NAME=events

# Database Configuration
DATABASE_URL=postgresql://user:password@db:5432/vms_analytics_db

# YOLO Model Paths
YOLO_MODEL=/app/weights/general/yolov8m.pt
GARBAGE_MODEL=/app/weights/garbage_detection/best.pt

# API Configuration
API_HOST=0.0.0.0
API_PORT=8069

# Snapshot Configuration
SNAPSHOTS_DIR=/app/snapshots
ENABLE_SNAPSHOTS=true

# Logging
LOG_LEVEL=INFO
```

### Camera Parameters

Each camera can be configured with:

- **Detection Settings**: Classes, confidence threshold, ROI zones
- **Tracking Settings**: Enable/disable tracking, buffer frames, dwell time
- **Motion Settings**: Motion threshold, cooldown periods
- **ANPR Settings**: Enable/disable, cooldown periods
- **Garbage Detection**: Enable/disable, confidence threshold, tracking
- **Retention**: Number of days to retain events (1-365)

See [API Documentation](#api-documentation) for detailed parameter options.

## API Documentation

### Camera Management

#### Register Camera
```http
POST /api/cameras
Content-Type: application/json

[
  {
    "camera_id": "camera_001",
    "camera_name": "Main Entrance",
    "stream_url": "rtsp://...",
    "parameters": {
      "enable_object_detection": true,
      "detection_classes": ["person", "car"],
      "confidence_threshold": 0.5,
      "retention_days": 30
    }
  }
]
```

#### List Cameras
```http
GET /api/cameras
```

#### Get Camera
```http
GET /api/cameras/{camera_id}
```

#### Delete Camera
```http
DELETE /api/cameras/{camera_id}
```

### Event Management

#### List Events
```http
GET /api/events?camera_id=camera_001&event_type=detection&page=1&page_size=50
```

Query Parameters:
- `camera_id`: Filter by camera ID
- `event_type`: Filter by event type (detection, motion, anpr, tracking)
- `object_class`: Filter by object class (person, car, truck, garbage)
- `start_time`: Start timestamp (ISO format)
- `end_time`: End timestamp (ISO format)
- `page`: Page number (default: 1)
- `page_size`: Items per page (default: 50, max: 500)

#### Get Event
```http
GET /api/events/{event_id}
```

#### Get Event Snapshot
```http
GET /api/events/{event_id}/snapshot
```

#### Get Event Statistics
```http
GET /api/events/stats?camera_id=camera_001
```

#### Delete Event
```http
DELETE /api/events/{event_id}?delete_snapshot=true
```

### Retention Management

#### Get Retention Statistics
```http
GET /api/retention/stats
```

#### Trigger Cleanup
```http
POST /api/retention/cleanup
```

#### Trigger Camera Cleanup
```http
POST /api/retention/cleanup/{camera_id}
```

#### Scheduler Status
```http
GET /api/retention/scheduler/status
```

### Health Check

```http
GET /api/health
```

For detailed API documentation, see:
- [API Payload Reference](docs/API_PAYLOAD_REFERENCE.md)
- [API Request/Response Examples](docs/API_REQUEST_RESPONSE.md)
- [Postman Collection](docs/Analytics_API.postman_collection.json)

## Development

### Local Setup

1. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Set up environment**:
   ```bash
   cp .env.example .env
   # Edit .env with your local configuration
   ```

3. **Initialize database**:
   ```bash
   # Run SQL migrations if needed
   psql -U your_user -d your_db -f sql/init_db.sql
   ```

4. **Run the service**:
   ```bash
   uvicorn app.main:app --host 0.0.0.0 --port 8069 --reload
   ```

### Project Structure

```
analytics_v2/
├── app/
│   ├── __init__.py
│   ├── main.py                 # FastAPI application entry point
│   ├── api/                    # API endpoints
│   │   ├── cameras.py          # Camera management endpoints
│   │   └── events.py           # Event management endpoints
│   ├── core/                   # Core infrastructure
│   │   ├── config.py           # Configuration management
│   │   ├── database.py         # Database connection
│   │   └── redis_client.py     # Redis Pub/Sub client
│   ├── models/                 # Data models
│   │   ├── db_models.py        # SQLAlchemy models
│   │   └── event_models.py     # Pydantic models
│   ├── services/               # Analytics services
│   │   ├── detection.py        # Object detection + tracking
│   │   ├── motion.py           # Motion detection
│   │   ├── anpr.py             # ANPR detection
│   │   ├── garbage_detection.py # Garbage detection
│   │   ├── garbage_tracker.py  # Garbage tracking
│   │   ├── event_filter.py     # Event filtering
│   │   ├── video_worker.py     # Camera processing
│   │   ├── retention.py        # Retention service
│   │   └── retention_scheduler.py # Retention scheduler
│   ├── utils/                  # Utilities
│   │   ├── logger.py           # Logging utility
│   │   └── snapshot.py         # Snapshot management
│   └── weights/                # Model weights (not in git)
│       ├── general/
│       │   └── yolov8m.pt
│       └── garbage_detection/
│           └── best.pt
├── docs/                       # Documentation
├── examples/                   # Example scripts
├── sql/                        # SQL migration scripts
├── Dockerfile                  # Docker image definition
├── docker-compose.yml          # Docker Compose configuration
├── requirements.txt            # Python dependencies
└── README.md                   # This file
```

### Running Tests

See example scripts in the `examples/` directory:
- `test_snapshots.py` - Test snapshot functionality
- `test_track_deduplication.py` - Test tracking deduplication
- `retention_demo.py` - Test retention service
- `example_event_filtering.py` - Test event filtering

## Deployment

### Docker Build & Push

```bash
DOCKER_NAMESPACE=dockared VERSION=1.0.0 ./build-and-push.sh
```

### Docker Deploy

```bash
DOCKER_NAMESPACE=dockared VERSION=1.0.0 ./deploy.sh
```

### Docker Compose

```bash
# Start services
docker compose up -d

# View logs
docker compose logs -f analytics-service

# Stop services
docker compose down

# Check status
docker compose ps
```

### Production Considerations

- **Database**: Use managed PostgreSQL service or dedicated database server
- **Redis**: Use managed Redis service or dedicated Redis server
- **Storage**: Configure persistent volumes for snapshots
- **Monitoring**: Set up logging and monitoring for production
- **Scaling**: Consider horizontal scaling for multiple camera streams
- **Security**: Use environment variables for sensitive configuration
- **Backup**: Implement database backup strategy

See [Deployment Checklist](docs/DEPLOYMENT_CHECKLIST.md) for detailed deployment guidance.

## Documentation

### Feature Documentation

- [Quick Start Guide](docs/QUICKSTART.md)
- [Snapshot Feature](docs/SNAPSHOT_FEATURE.md)
- [Event Filtering](docs/EVENT_FILTERING.md)
- [Event Retention](docs/EVENT_RETENTION.md)
- [Object Tracking](docs/TRACKING_IMPLEMENTATION_GUIDE.md)
- [Garbage Detection](docs/GARBAGE_DETECTION_INTEGRATION.md)
- [Camera Name Feature](docs/CAMERA_NAME_FEATURE.md)

### Integration Guides

- [Django Integration](docs/DJANGO_INTEGRATION.md)
- [Redis Pub/Sub Implementation](docs/REDIS_PUBSUB_IMPLEMENTATION.md)
- [Migration Guide](docs/MIGRATION_GUIDE.md)

### API References

- [API Payload Reference](docs/API_PAYLOAD_REFERENCE.md)
- [API Request/Response](docs/API_REQUEST_RESPONSE.md)
- [Event Types Reference](docs/EVENT_TYPES_REFERENCE.md)
- [Retention API Reference](docs/RETENTION_API_REFERENCE.md)
- [Postman Collection](docs/Analytics_API.postman_collection.json)

### Technical Documentation

- [Project Summary](docs/PROJECT_SUMMARY.md)
- [Implementation Status](docs/IMPLEMENTATION_COMPLETE.md)
- [PyTorch Compatibility Fix](docs/PYTORCH_FIX.md)

## License

[Add your license information here]

## Support

For issues, questions, or contributions, please [open an issue](link-to-issues) or contact the development team.

---

**Version**: 1.0.0  
**Service URL**: `http://localhost:8069` (default)  
**API Documentation**: Available at `/docs` when running (FastAPI auto-generated docs)
