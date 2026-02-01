# VMS AIvan Analytics Service - Developer Guide

## Table of Contents

1. [Project Structure](#project-structure)
2. [Tech Stack & Versions](#tech-stack--versions)
3. [How to Build & Run Locally](#how-to-build--run-locally)
4. [How to Deploy to Production/Staging](#how-to-deploy-to-productionstaging)
5. [Environment Variable Details](#environment-variable-details)
6. [API Documentation](#api-documentation)
7. [Development Workflow](#development-workflow)
8. [Architecture Overview](#architecture-overview)
9. [Adding New Features](#adding-new-features)

---

## Project Structure

The VMS AIvan Analytics Service is a FastAPI-based video analytics service located in the `aivan-analytics/` directory. The project follows a modular architecture with clear separation of concerns.

```
aivan-analytics/
├── app/                          # Main application package
│   ├── __init__.py
│   ├── main.py                  # FastAPI application entry point
│   ├── api/                     # API endpoints
│   │   ├── __init__.py
│   │   ├── cameras.py           # Camera management endpoints
│   │   └── events.py            # Event management endpoints
│   ├── core/                    # Core infrastructure
│   │   ├── __init__.py
│   │   ├── config.py            # Configuration management (Pydantic Settings)
│   │   ├── database.py          # Database connection and models
│   │   └── redis_client.py      # Redis Pub/Sub client
│   ├── models/                  # Data models
│   │   ├── __init__.py
│   │   ├── db_models.py         # SQLAlchemy ORM models
│   │   └── event_models.py      # Pydantic request/response models
│   ├── services/                # Analytics services
│   │   ├── __init__.py
│   │   ├── detection.py         # Object detection + tracking (YOLOv8 + ByteTrack)
│   │   ├── motion.py            # Motion detection service
│   │   ├── anpr.py              # ANPR (Automatic Number Plate Recognition)
│   │   ├── garbage_detection.py # Garbage detection service
│   │   ├── garbage_tracker.py   # Garbage tracking service
│   │   ├── event_filter.py      # Event filtering and deduplication
│   │   ├── video_worker.py      # Camera stream processing worker
│   │   ├── retention.py         # Event retention service
│   │   └── retention_scheduler.py # Retention scheduler (background tasks)
│   ├── utils/                   # Utility functions
│   │   ├── __init__.py
│   │   ├── logger.py            # Logging utility
│   │   └── snapshot.py          # Snapshot management utility
│   └── weights/                 # ML model weights (not in git)
│       ├── general/
│       │   └── yolov8m.pt       # YOLOv8 general detection model
│       └── garbage_detection/
│           └── best.pt          # Custom garbage detection model
├── examples/                    # Example scripts and demos
│   ├── compare_filtering_approaches.py
│   ├── example_event_filtering.py
│   ├── example_usage.sh
│   ├── pubsub_consumer_example.py
│   ├── retention_demo.py
│   ├── test_snapshots.py
│   ├── test_track_deduplication.py
│   └── test_track_deduplication_simple.py
├── sql/                         # SQL migration scripts
│   ├── init_db.sql              # Initial database schema
│   ├── add_camera_name_migration.sql
│   └── add_object_class_index_migration.sql
├── Dockerfile                   # Docker image definition
├── docker-compose.yml           # Docker Compose configuration
├── requirements.txt             # Python dependencies
├── build-and-push.sh            # Docker build and push script
├── deploy.sh                    # Deployment script
├── README.md                    # Project README
└── .env                         # Environment variables (not in git)
```

---

## Tech Stack & Versions

### Core Framework
- **Python**: 3.11
- **FastAPI**: 0.109.0
- **Uvicorn**: 0.27.0 (ASGI server)
- **Pydantic**: 2.5.3 (Data validation)
- **Pydantic Settings**: 2.1.0 (Configuration management)

### Key Dependencies

**API & Web Framework:**
- **fastapi**: 0.109.0 - Modern, fast web framework
- **uvicorn[standard]**: 0.27.0 - ASGI server
- **pydantic**: 2.5.3 - Data validation using Python type annotations
- **pydantic-settings**: 2.1.0 - Settings management

**Database & ORM:**
- **sqlalchemy**: 2.0.25 - SQL toolkit and ORM
- **psycopg2-binary**: 2.9.9 - PostgreSQL adapter
- **alembic**: 1.13.1 - Database migration tool

**Computer Vision & ML:**
- **ultralytics**: 8.1.0 - YOLOv8 object detection
- **opencv-python-headless**: 4.9.0.80 - Computer vision library
- **numpy**: 1.26.3 - Numerical computing
- **supervision**: >=0.19.0 - Computer vision utilities
- **pillow**: 10.2.0 - Image processing

**ANPR (License Plate Recognition):**
- **fast-alpr[onnx]**: 0.3.0 - Automatic License Plate Recognition

**Caching & Messaging:**
- **redis**: 5.0.1 - Redis client for Pub/Sub and caching

**Utilities:**
- **python-dotenv**: 1.0.0 - Environment variable management
- **python-multipart**: 0.0.6 - Multipart form data support

### External Services
- **PostgreSQL**: 14+ (Event storage database)
- **Redis**: 7+ (Pub/Sub for real-time event streaming)
- **RTSP Streams**: (Camera video streams)

---

## How to Build & Run Locally

### Prerequisites

1. **Python 3.11+**: Install Python 3.11 or higher
   ```bash
   # Check version
   python3 --version  # Should be 3.11 or higher
   ```

2. **PostgreSQL 14+**: Install and run PostgreSQL
   ```bash
   # On macOS (using Homebrew)
   brew install postgresql@14
   brew services start postgresql@14
   
   # On Ubuntu/Debian
   sudo apt-get install postgresql-14
   sudo systemctl start postgresql
   ```

3. **Redis 7+**: Install and run Redis
   ```bash
   # On macOS (using Homebrew)
   brew install redis
   brew services start redis
   
   # On Ubuntu/Debian
   sudo apt-get install redis-server
   sudo systemctl start redis-server
   ```

4. **FFmpeg**: Required for video processing
   ```bash
   # On macOS
   brew install ffmpeg
   
   # On Ubuntu/Debian
   sudo apt-get install ffmpeg
   ```

5. **Virtual Environment** (recommended):
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

### Initial Setup

1. **Navigate to analytics directory**:
   ```bash
   cd aivan-analytics
   ```

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Create `.env` file**:
   Create a `.env` file in the project root with the following variables:
   ```env
   # Redis Configuration
   REDIS_HOST=localhost
   REDIS_PORT=6379
   REDIS_DB=0
   REDIS_PASSWORD=
   REDIS_CHANNEL_NAME=events
   
   # Database Configuration
   DATABASE_URL=postgresql://vms_admin:password@localhost:5432/vms_analytics_db
   
   # YOLO Model Paths
   YOLO_MODEL=./app/weights/general/yolov8m.pt
   GARBAGE_MODEL=./app/weights/garbage_detection/best.pt
   
   # API Configuration
   API_HOST=0.0.0.0
   API_PORT=8069
   
   # Snapshot Configuration
   SNAPSHOTS_DIR=./snapshots
   ENABLE_SNAPSHOTS=true
   SNAPSHOT_FORMAT=jpg
   SNAPSHOT_QUALITY=80
   
   # Logging
   LOG_LEVEL=INFO
   
   # Docker Configuration (optional, for deployment)
   DOCKER_NAMESPACE=dockared
   VERSION=latest
   ```

4. **Create PostgreSQL database**:
   ```bash
   # Connect to PostgreSQL
   psql -U postgres
   
   # Create database and user
   CREATE DATABASE vms_analytics_db;
   CREATE USER vms_admin WITH PASSWORD 'password';
   GRANT ALL PRIVILEGES ON DATABASE vms_analytics_db TO vms_admin;
   \q
   ```

5. **Initialize database schema**:
   ```bash
   # Run SQL initialization script
   psql -U vms_admin -d vms_analytics_db -f sql/init_db.sql
   
   # Run additional migrations if needed
   psql -U vms_admin -d vms_analytics_db -f sql/add_camera_name_migration.sql
   psql -U vms_admin -d vms_analytics_db -f sql/add_object_class_index_migration.sql
   ```

6. **Download model weights** (if not present):
   ```bash
   # Create weights directories
   mkdir -p app/weights/general
   mkdir -p app/weights/garbage_detection
   
   # Download YOLOv8 model (will be downloaded automatically on first use)
   # Or manually download from Ultralytics
   ```

### Running Development Server

1. **Start Redis** (if not already running):
   ```bash
   redis-server
   # Or if installed via Homebrew
   brew services start redis
   ```

2. **Run the service**:
   ```bash
   # Using uvicorn directly
   uvicorn app.main:app --host 0.0.0.0 --port 8069 --reload
   
   # Or using Python module
   python -m uvicorn app.main:app --host 0.0.0.0 --port 8069 --reload
   ```

3. **Access the application**:
   - API: `http://localhost:8069/`
   - API Documentation: `http://localhost:8069/docs` (Swagger UI)
   - Alternative Docs: `http://localhost:8069/redoc` (ReDoc)

### Running with Docker (Local Development)

1. **Create Docker network** (if not exists):
   ```bash
   docker network create vms_network
   ```

2. **Start services**:
   ```bash
   docker-compose up -d
   ```

3. **View logs**:
   ```bash
   docker-compose logs -f analytics-service
   ```

4. **Stop services**:
   ```bash
   docker-compose down
   ```

### Running Example Scripts

The `examples/` directory contains several example scripts:

```bash
# Test snapshot functionality
python examples/test_snapshots.py

# Test event filtering
python examples/example_event_filtering.py

# Test retention service
python examples/retention_demo.py

# Test tracking deduplication
python examples/test_track_deduplication.py

# Example usage script
bash examples/example_usage.sh
```

### Testing API Endpoints

```bash
# Health check
curl http://localhost:8069/

# List cameras
curl http://localhost:8069/api/cameras

# Register a camera
curl -X POST http://localhost:8069/api/cameras \
  -H "Content-Type: application/json" \
  -d '{
    "camera_id": "test_camera",
    "camera_name": "Test Camera",
    "stream_url": "rtsp://your-stream-url",
    "parameters": {
      "enable_object_detection": true,
      "detection_classes": ["person", "car"],
      "confidence_threshold": 0.5
    }
  }'

# List events
curl http://localhost:8069/api/events?camera_id=test_camera

# Health check
curl http://localhost:8069/api/health
```

---

## How to Deploy to Production/Staging

### Prerequisites for Deployment

1. **Docker**: Docker installed and running
2. **Docker Compose**: Docker Compose v2.0+
3. **Docker Hub Account**: For pushing images (or use private registry)
4. **Server Access**: SSH access to deployment server
5. **PostgreSQL**: PostgreSQL database (can be on same server or separate)
6. **Redis**: Redis server (can be on same server or separate)

### Building Docker Images

**Using the build script**:
```bash
cd aivan-analytics

# Set environment variables
export DOCKER_NAMESPACE=your-dockerhub-username
export VERSION=latest  # or v1.0.0, staging, etc.

# Build and push
./build-and-push.sh
```

**Manual Docker build**:
```bash
# Build analytics service
docker buildx build \
  --platform linux/amd64 \
  --tag username/aivan-analytics:latest \
  --push \
  --file Dockerfile \
  .
```

**What the build script does**:
- Creates a Docker buildx builder for multi-platform builds
- Builds the image for `linux/amd64` platform
- Pushes the image to Docker Hub
- Uses Python 3.11-slim base image
- Installs system dependencies (OpenCV, FFmpeg, etc.)
- Installs Python dependencies from `requirements.txt`
- Sets up the application with proper working directory

### Deploying to Server

**Using the deployment script**:
```bash
# On the deployment server
cd /path/to/deployment

# Set version
export DOCKER_NAMESPACE=your-dockerhub-username
export VERSION=latest

# Deploy
./deploy.sh
```

**Manual Docker deployment**:

1. **Create Docker network** (if not exists):
   ```bash
   docker network create vms_network
   ```

2. **Create required volumes**:
   ```bash
   docker volume create aivan_analytics_snapshots
   ```

3. **Create `.env` file** on the server with production values:
   ```env
   REDIS_HOST=redis-host
   REDIS_PORT=6379
   REDIS_DB=0
   REDIS_PASSWORD=your-redis-password
   REDIS_CHANNEL_NAME=events
   
   DATABASE_URL=postgresql://user:password@db-host:5432/vms_analytics_db
   
   YOLO_MODEL=/app/weights/general/yolov8m.pt
   GARBAGE_MODEL=/app/weights/garbage_detection/best.pt
   
   API_HOST=0.0.0.0
   API_PORT=8069
   
   SNAPSHOTS_DIR=/app/snapshots
   ENABLE_SNAPSHOTS=true
   
   LOG_LEVEL=INFO
   ```

4. **Deploy analytics service**:
   ```bash
   # Pull the latest image
   docker pull username/aivan-analytics:latest
   
   # Stop and remove existing container (if exists)
   docker stop aivan-analytics || true
   docker rm aivan-analytics || true
   
   # Run the new container
   docker run -d \
     --name aivan-analytics \
     --restart unless-stopped \
     --network vms_network \
     --env-file .env \
     -p 8069:8069 \
     -v aivan_analytics_snapshots:/app/snapshots \
     username/aivan-analytics:latest
   ```

### Using Docker Compose for Deployment

```bash
# Set environment variables
export DOCKER_NAMESPACE=your-dockerhub-username
export VERSION=latest

# Pull latest images
docker-compose pull

# Start services
docker-compose up -d

# View logs
docker-compose logs -f analytics-service
```

### Staging Deployment

For staging environments, use a different tag:

```bash
# Build and push staging version
export VERSION=staging
./build-and-push.sh

# Deploy staging version
export VERSION=staging
./deploy.sh
```

### Production Deployment with Nginx Reverse Proxy

For production, it's recommended to use Nginx as a reverse proxy:

**Nginx configuration** (`/etc/nginx/sites-available/aivan-analytics`):
```nginx
upstream aivan_analytics {
    server localhost:8069;
}

server {
    listen 80;
    server_name analytics.your-domain.com;

    # Redirect HTTP to HTTPS
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name analytics.your-domain.com;

    ssl_certificate /etc/letsencrypt/live/analytics.your-domain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/analytics.your-domain.com/privkey.pem;

    # Security headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;

    # Proxy settings
    location / {
        proxy_pass http://aivan_analytics;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # WebSocket support (if needed)
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
```

**Enable SSL with Let's Encrypt**:
```bash
# Install Certbot
sudo apt-get install certbot python3-certbot-nginx

# Obtain SSL certificate
sudo certbot --nginx -d analytics.your-domain.com
```

### Container Management

**Useful Docker commands**:
```bash
# View container logs
docker logs -f aivan-analytics

# Check container status
docker ps | grep aivan-analytics

# Stop container
docker stop aivan-analytics

# Start container
docker start aivan-analytics

# Restart container
docker restart aivan-analytics

# Remove container
docker rm -f aivan-analytics

# View container resource usage
docker stats aivan-analytics

# Execute commands in container
docker exec -it aivan-analytics python -c "from app.core.database import check_db_connection; print(check_db_connection())"
```

### Health Checks

The application provides health check endpoints:

```bash
# Basic health check
curl http://localhost:8069/

# Detailed health check
curl http://localhost:8069/api/health
```

Docker containers include health checks that automatically restart unhealthy containers.

---

## Environment Variable Details

The analytics service uses environment variables for configuration, loaded from a `.env` file in the project root using `pydantic-settings`.

### Environment File Location

The `.env` file should be located in the `aivan-analytics/` directory (project root). This file should **NOT** be committed to version control.

### Environment Configuration Structure

**Required Variables**:

| Variable | Type | Description | Example |
|----------|------|-------------|---------|
| `DATABASE_URL` | `string` | PostgreSQL connection string | `postgresql://user:pass@host:5432/db` |
| `REDIS_HOST` | `string` | Redis hostname | `localhost` |
| `REDIS_PORT` | `integer` | Redis port | `6379` |

**Redis Configuration**:

| Variable | Type | Description | Example |
|----------|------|-------------|---------|
| `REDIS_HOST` | `string` | Redis hostname | `localhost` |
| `REDIS_PORT` | `integer` | Redis port | `6379` |
| `REDIS_DB` | `integer` | Redis database number | `0` |
| `REDIS_PASSWORD` | `string` | Redis password (optional) | `your-password` |
| `REDIS_CHANNEL_NAME` | `string` | Pub/Sub channel name | `events` |

**Database Configuration**:

| Variable | Type | Description | Example |
|----------|------|-------------|---------|
| `DATABASE_URL` | `string` | Full database connection URL | `postgresql://user:password@localhost:5432/vms_analytics_db` |

**Model Configuration**:

| Variable | Type | Description | Example |
|----------|------|-------------|---------|
| `YOLO_MODEL` | `string` | Path to YOLOv8 model file | `/app/weights/general/yolov8m.pt` |
| `GARBAGE_MODEL` | `string` | Path to garbage detection model | `/app/weights/garbage_detection/best.pt` |

**API Configuration**:

| Variable | Type | Description | Example |
|----------|------|-------------|---------|
| `API_HOST` | `string` | API host address | `0.0.0.0` |
| `API_PORT` | `integer` | API port | `8069` |

**Snapshot Configuration**:

| Variable | Type | Description | Example |
|----------|------|-------------|---------|
| `SNAPSHOTS_DIR` | `string` | Directory for storing snapshots | `/app/snapshots` |
| `ENABLE_SNAPSHOTS` | `boolean` | Enable/disable snapshot capture | `true` |
| `SNAPSHOT_FORMAT` | `string` | Snapshot image format | `jpg` |
| `SNAPSHOT_QUALITY` | `integer` | Snapshot JPEG quality (1-100) | `80` |

**Logging Configuration**:

| Variable | Type | Description | Example |
|----------|------|-------------|---------|
| `LOG_LEVEL` | `string` | Logging level | `INFO`, `DEBUG`, `WARNING`, `ERROR` |

**Docker Configuration** (optional, for deployment):

| Variable | Type | Description | Example |
|----------|------|-------------|---------|
| `DOCKER_NAMESPACE` | `string` | Docker Hub namespace | `dockared` |
| `VERSION` | `string` | Image version tag | `latest` |

### Using Environment Variables

Environment variables are loaded in `app/core/config.py` using `pydantic-settings`:

```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    redis_host: str = "redis"
    redis_port: int = 6379
    # ... other settings
    
    class Config:
        env_file = ".env"
        case_sensitive = False
```

### Production vs Development

**Development** (`.env`):
```env
REDIS_HOST=localhost
REDIS_PORT=6379
DATABASE_URL=postgresql://user:pass@localhost:5432/vms_analytics_db
LOG_LEVEL=DEBUG
```

**Production** (`.env`):
```env
REDIS_HOST=redis-host
REDIS_PORT=6379
REDIS_PASSWORD=secure-password
DATABASE_URL=postgresql://user:pass@db-host:5432/vms_analytics_db
LOG_LEVEL=INFO
ENABLE_SNAPSHOTS=true
```

### Security Considerations

1. **Never commit `.env` files** to version control
2. **Use strong database passwords** in production
3. **Use HTTPS** for all production endpoints
4. **Secure Redis** with password authentication in production
5. **Limit network access** to database and Redis
6. **Use environment-specific configurations** for different deployment targets
7. **Rotate secrets regularly** in production

---

## API Documentation

### Accessing API Documentation

Once the server is running, access the API documentation at:

- **Swagger UI**: `http://localhost:8069/docs`
- **ReDoc**: `http://localhost:8069/redoc`
- **OpenAPI JSON**: `http://localhost:8069/openapi.json`

### API Endpoints

#### Camera Management

**Register Camera(s)**:
```http
POST /api/cameras
Content-Type: application/json

[
  {
    "camera_id": "camera_001",
    "camera_name": "Main Entrance",
    "stream_url": "rtsp://your-camera-stream-url",
    "parameters": {
      "enable_object_detection": true,
      "enable_motion_detection": true,
      "detection_classes": ["person", "car"],
      "confidence_threshold": 0.5,
      "retention_days": 30
    }
  }
]
```

**List Cameras**:
```http
GET /api/cameras
```

**Get Camera**:
```http
GET /api/cameras/{camera_id}
```

**Delete Camera**:
```http
DELETE /api/cameras/{camera_id}
```

#### Event Management

**List Events**:
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

**Get Event**:
```http
GET /api/events/{event_id}
```

**Get Event Snapshot**:
```http
GET /api/events/{event_id}/snapshot
```

**Get Event Statistics**:
```http
GET /api/events/stats?camera_id=camera_001
```

**Delete Event**:
```http
DELETE /api/events/{event_id}?delete_snapshot=true
```

#### Retention Management

**Get Retention Statistics**:
```http
GET /api/retention/stats
```

**Trigger Cleanup**:
```http
POST /api/retention/cleanup
```

**Trigger Camera Cleanup**:
```http
POST /api/retention/cleanup/{camera_id}
```

**Scheduler Status**:
```http
GET /api/retention/scheduler/status
```

#### Health Check

```http
GET /api/health
```

Response includes:
- Service status
- Database connection status
- Redis connection status
- Active cameras count
- Retention scheduler status

---

## Development Workflow

### Creating a New Service

1. **Create service file** in `app/services/`:
   ```python
   # app/services/my_service.py
   from app.utils.logger import get_logger
   
   logger = get_logger(__name__)
   
   class MyService:
       def __init__(self):
           logger.info("Initializing MyService")
       
       def process(self, data):
           # Service logic
           pass
   ```

2. **Import and use** in other modules:
   ```python
   from app.services.my_service import MyService
   
   my_service = MyService()
   ```

### Creating API Endpoints

1. **Create endpoint** in `app/api/`:
   ```python
   # app/api/my_endpoint.py
   from fastapi import APIRouter, HTTPException
   from app.models.event_models import MyRequestModel, MyResponseModel
   
   router = APIRouter(prefix="/api", tags=["my-feature"])
   
   @router.post("/my-endpoint", response_model=MyResponseModel)
   async def my_endpoint(request: MyRequestModel):
       # Endpoint logic
       return MyResponseModel(...)
   ```

2. **Register router** in `app/main.py`:
   ```python
   from app.api.my_endpoint import router as my_router
   
   app.include_router(my_router)
   ```

### Creating Data Models

1. **Create Pydantic models** in `app/models/event_models.py`:
   ```python
   from pydantic import BaseModel
   from typing import Optional
   
   class MyRequestModel(BaseModel):
       field1: str
       field2: Optional[int] = None
   
   class MyResponseModel(BaseModel):
       id: str
       status: str
   ```

2. **Create SQLAlchemy models** in `app/models/db_models.py`:
   ```python
   from sqlalchemy import Column, String, Integer
   from app.core.database import Base
   
   class MyTable(Base):
       __tablename__ = "my_table"
       
       id = Column(String, primary_key=True)
       field1 = Column(String)
       field2 = Column(Integer)
   ```

3. **Create database migration**:
   ```sql
   -- sql/add_my_table_migration.sql
   CREATE TABLE IF NOT EXISTS my_table (
       id VARCHAR PRIMARY KEY,
       field1 VARCHAR NOT NULL,
       field2 INTEGER
   );
   ```

### Adding New Detection Types

1. **Create detection service** in `app/services/`:
   ```python
   # app/services/my_detection.py
   from app.utils.logger import get_logger
   import cv2
   
   logger = get_logger(__name__)
   
   class MyDetectionService:
       def __init__(self):
           # Initialize model
           pass
       
       def detect(self, frame):
           # Detection logic
           return detections
   ```

2. **Integrate with video worker** in `app/services/video_worker.py`:
   ```python
   from app.services.my_detection import MyDetectionService
   
   class VideoWorker:
       def __init__(self):
           self.my_detection = MyDetectionService()
       
       def process_frame(self, frame):
           if self.config.enable_my_detection:
               detections = self.my_detection.detect(frame)
               # Process detections
   ```

### Code Formatting

The project follows PEP 8 style guidelines. Consider using:

```bash
# Install formatter
pip install black

# Format all Python files
black app/

# Check formatting without making changes
black --check app/
```

### Testing

Create test scripts in the `examples/` directory:

```python
# examples/test_my_feature.py
import requests

def test_my_feature():
    response = requests.get("http://localhost:8069/api/my-endpoint")
    print(response.json())

if __name__ == "__main__":
    test_my_feature()
```

---

## Architecture Overview

### System Architecture

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

### Key Components

**Video Worker** (`app/services/video_worker.py`):
- Manages camera stream connections
- Processes video frames
- Coordinates detection services
- Handles event generation and publishing

**Detection Service** (`app/services/detection.py`):
- YOLOv8-based object detection
- ByteTrack object tracking
- Generates detection and tracking events

**Motion Detection** (`app/services/motion.py`):
- Frame differencing
- Background subtraction
- Motion event generation

**ANPR Service** (`app/services/anpr.py`):
- License plate detection and recognition
- Text extraction from plates
- ANPR event generation

**Garbage Detection** (`app/services/garbage_detection.py`):
- Custom YOLO model for garbage detection
- Optional tracking support
- Garbage event generation

**Event Filter** (`app/services/event_filter.py`):
- Cooldown period management
- Event deduplication
- Prevents event flooding

**Retention Service** (`app/services/retention.py`):
- Event retention policy management
- Automatic cleanup of expired events
- Per-camera retention configuration

**Retention Scheduler** (`app/services/retention_scheduler.py`):
- Background task scheduler
- Periodic cleanup execution
- Scheduler status management

### Data Flow

1. **Camera Registration**: API receives camera configuration → Video Worker starts processing stream
2. **Frame Processing**: Video stream → Frame extraction → Detection services → Event generation
3. **Event Publishing**: Events → Event Filter → Redis Pub/Sub → External consumers
4. **Event Storage**: Events → Database storage → Retention service → Cleanup

---

## Adding New Features

### Adding a New Detection Type

1. **Create detection service**:
   ```python
   # app/services/new_detection.py
   from app.utils.logger import get_logger
   
   logger = get_logger(__name__)
   
   class NewDetectionService:
       def __init__(self, model_path):
           # Load model
           pass
       
       def detect(self, frame):
           # Detection logic
           return results
   ```

2. **Add to camera parameters** in `app/models/event_models.py`:
   ```python
   class CameraParameters(BaseModel):
       enable_new_detection: bool = False
       new_detection_threshold: float = 0.5
   ```

3. **Integrate in video worker** (`app/services/video_worker.py`):
   ```python
   from app.services.new_detection import NewDetectionService
   
   if self.config.parameters.enable_new_detection:
       detections = self.new_detection.detect(frame)
   ```

4. **Add event type** to database schema if needed

### Adding a New API Endpoint

1. **Create endpoint** in `app/api/`:
   ```python
   # app/api/new_feature.py
   from fastapi import APIRouter
   
   router = APIRouter(prefix="/api", tags=["new-feature"])
   
   @router.get("/new-endpoint")
   async def new_endpoint():
       return {"message": "New feature"}
   ```

2. **Register in main.py**:
   ```python
   from app.api.new_feature import router as new_feature_router
   app.include_router(new_feature_router)
   ```

### Adding Database Migrations

1. **Create SQL migration file**:
   ```sql
   -- sql/add_new_table_migration.sql
   CREATE TABLE IF NOT EXISTS new_table (
       id SERIAL PRIMARY KEY,
       created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
   );
   
   CREATE INDEX IF NOT EXISTS idx_new_table_created_at ON new_table(created_at);
   ```

2. **Run migration**:
   ```bash
   psql -U vms_admin -d vms_analytics_db -f sql/add_new_table_migration.sql
   ```

---

## Additional Resources

### Documentation
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Pydantic Documentation](https://docs.pydantic.dev/)
- [SQLAlchemy Documentation](https://docs.sqlalchemy.org/)
- [Ultralytics YOLOv8](https://docs.ultralytics.com/)
- [OpenCV Documentation](https://docs.opencv.org/)
- [Redis Documentation](https://redis.io/docs/)
- [PostgreSQL Documentation](https://www.postgresql.org/docs/)

### Getting Help
1. Check the [FastAPI documentation](https://fastapi.tiangolo.com/)
2. Review error messages in logs: `docker logs -f aivan-analytics`
3. Check API documentation: `http://localhost:8069/docs`
4. Verify environment configuration matches your deployment target
5. Review example scripts in `examples/` directory

### Common Issues

**Database Connection Issues**:
- Ensure PostgreSQL is running and accessible
- Check `DATABASE_URL` in `.env`
- Verify database credentials and permissions
- Check network connectivity

**Redis Connection Issues**:
- Ensure Redis is running
- Check `REDIS_HOST` and `REDIS_PORT` in `.env`
- Verify Redis is accessible from the application
- Check Redis password if configured

**Camera Stream Issues**:
- Verify RTSP stream URL is accessible
- Check network connectivity to camera
- Review video worker logs for stream errors
- Ensure FFmpeg is installed

**Model Loading Issues**:
- Verify model files exist at specified paths
- Check file permissions
- Ensure model files are compatible versions
- Review logs for model loading errors

**Event Publishing Issues**:
- Verify Redis Pub/Sub is working
- Check `REDIS_CHANNEL_NAME` configuration
- Review event filter logs
- Ensure consumers are listening to correct channel

**Snapshot Issues**:
- Check `SNAPSHOTS_DIR` exists and is writable
- Verify disk space availability
- Check file permissions
- Review snapshot utility logs

---

**End of Developer Guide**

