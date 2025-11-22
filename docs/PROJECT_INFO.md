
### 🚀 Project Goal

Create a **standalone analytics service** in **Python** that:

* Accepts **camera configuration payloads** via REST API
* Performs **object detection**, **motion detection**, and **ANPR** (Automatic Number Plate Recognition)
* Generates structured **event objects** (detection / motion / anpr)
* Publishes all events to a **Redis Stream**
* Is **Dockerized**, **environment-based** (using `.env`), and easily pluggable with an existing **Redis instance**
* The analytics loop should use **YOLOv8** for object detection (via `ultralytics` library).

---

### 🧩 Functional Requirements

#### 1. REST API (FastAPI or Flask)

Expose endpoints like:

* `POST /api/cameras` → Register/start processing a camera stream
* `GET /api/cameras` → List all active cameras
* `DELETE /api/cameras/{camera_id}` → Stop processing a camera
* `GET /api/health` → Health check

Each camera payload will look like:

```json
[
  {
    "camera_id": "7e793c44-5960-4d40-903f-9c2cf0a17903",
    "status": "active",
    "stream_url": "rtsp://user:password@172.16.34.2:554/media/video1",
    "parameters": {
      "detection_classes": ["person", "car", "truck"],
      "confidence_threshold": 0.5,
      "roi_zones": [],
      "enable_motion_detection": true,
      "enable_object_detection": true,
      "enable_anpr": false,
      "motion_threshold": 0.1,
      "frame_skip": 1,
      "max_fps": 30
    }
  }
]
```

---

#### 2. Video Analytics Workers

Each active camera runs in a **background process/thread**, performing:

* **Object detection** using YOLOv8 (Ultralytics)
* **Motion detection** using OpenCV frame differencing
* **ANPR** (optional, using EasyOCR or PaddleOCR)

Each processed frame generates an event JSON, e.g.:

##### Detection Event

```json
{
  "event_type": "detection",
  "camera_id": "camera-001",
  "timestamp": "2025-10-09T13:29:12Z",
  "detections": [
    {
      "class_name": "person",
      "confidence": 0.95,
      "bounding_box": { "x": 0.1, "y": 0.2, "width": 0.3, "height": 0.4 }
    }
  ],
  "frame_number": 1000,
  "model_info": { "model_type": "yolov8n", "version": "8.0.196" }
}
```

##### Motion Event

```json
{
  "event_type": "motion",
  "camera_id": "camera-001",
  "motion_intensity": 0.8,
  "affected_area_percentage": 0.15,
  "frame_number": 1000
}
```

##### ANPR Event

```json
{
  "event_type": "anpr",
  "camera_id": "camera-001",
  "anpr_result": {
    "license_plate": "ABC123",
    "confidence": 0.92,
    "region": "CA"
  }
}
```

---

#### 3. Redis Integration

* Publish every event JSON to a **Redis Stream** (e.g. `stream:events`)
* Each message contains:

  * `event_type`, `camera_id`, `timestamp`, and `payload`
* Your Django app will **consume these Redis streams** asynchronously to update its database and dashboards.

Example publish code:

```python
import redis, json
r = redis.Redis(host="redis", port=6379, db=0)
r.xadd("stream:events", {"data": json.dumps(event_data)})
```

---

#### 4. Configuration & Environment

Use a `.env` file for settings:

```
REDIS_HOST=redis
REDIS_PORT=6379
YOLO_MODEL=yolov8n.pt
LOG_LEVEL=INFO
```

Use `pydantic.BaseSettings` or `python-dotenv` to load these.

---

#### 5. Docker Setup

**Dockerfile** should:

* Start from `python:3.11-slim`
* Install dependencies: `ultralytics`, `opencv-python`, `redis`, `fastapi`, `uvicorn`, `python-dotenv`
* Copy the app code and expose port `8069`
* Set entrypoint as:
  `uvicorn app.main:app --host 0.0.0.0 --port 8069`

**docker-compose.yml**:

```yaml
version: "3.8"
services:
  analytics-service:
    build: .
    env_file: .env
    ports:
      - "8069:8069"
    networks:
      - vms_network

networks:
  vms_network:
    external: true
```

**Note**: Connects to existing Redis on `vms_network`

---

#### 6. Folder Structure

```
analytics_service/
│
├── app/
│   ├── main.py               # FastAPI entrypoint
│   ├── api/
│   │   └── cameras.py        # Endpoints for camera management
│   ├── core/
│   │   ├── config.py         # Env + Redis setup
│   │   ├── redis_client.py   # Redis wrapper
│   ├── services/
│   │   ├── video_worker.py   # Camera thread & processing logic
│   │   ├── motion.py         # Motion detection
│   │   ├── detection.py      # YOLO inference
│   │   ├── anpr.py           # License plate recognition
│   ├── models/
│   │   ├── event_models.py   # Pydantic models for all event types
│   └── utils/
│       ├── logger.py
│
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
└── .env
```

---

#### 7. Tech Stack

* **FastAPI** — REST API
* **Redis Streams** — Message bus
* **YOLOv8 (Ultralytics)** — Object detection
* **OpenCV** — Frame reading + motion detection
* **EasyOCR or PaddleOCR** — ANPR
* **Pydantic** — Type validation
* **Docker** — Containerization

---

### 🧩 Example Command

Once built, you should be able to run:

```bash
docker compose up --build
```

Then register a camera:

```bash
curl -X POST http://localhost:8069/api/cameras \
     -H "Content-Type: application/json" \
     -d '[{"camera_id": "cam-1", "stream_url": "rtsp://...", "parameters": {...}}]'
```

---

### ✅ Deliverables

The generated project should include:

* Working REST API with FastAPI
* Background YOLO and motion processing per camera
* Redis stream event publishing
* Dockerfile + docker-compose.yml
* Configurable `.env`
* Example logs for detection events