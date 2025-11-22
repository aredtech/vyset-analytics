# Quick Start Guide

## Prerequisites

- Docker and Docker Compose installed
- External Docker network named `vms_network`
- Redis running on the `vms_network` (accessible at `redis:6379`)
- At least 4GB RAM available
- RTSP camera stream or video file URL

## Installation & Setup

### 1. Ensure Prerequisites

```bash
# Create the network if it doesn't exist
docker network create vms_network

# Verify Redis is running on vms_network
docker network inspect vms_network | grep redis
```

### 2. Start the Service

```bash
cd /Users/rajumandal/OldFiles/VMS2.0/analytics
docker compose up --build
```

Wait for the service to start. You should see:
```
✓ Analytics service started
✓ Connected to Redis
✓ YOLO model loaded
```

### 3. Test the API

Open a new terminal and check if the service is running:

```bash
curl http://localhost:8069/api/health
```

Expected output:
```json
{
  "status": "healthy",
  "redis_connected": true,
  "active_cameras": 0
}
```

### 4. Register a Camera

Replace the stream URL with your actual RTSP URL:

```bash
curl -X POST http://localhost:8069/api/cameras \
  -H "Content-Type: application/json" \
  -d '[
    {
      "camera_id": "cam-001",
      "status": "active",
      "stream_url": "rtsp://user:password@your-camera-ip:554/stream",
      "parameters": {
        "detection_classes": ["person", "car", "truck"],
        "confidence_threshold": 0.5,
        "enable_motion_detection": true,
        "enable_object_detection": true,
        "enable_anpr": false,
        "frame_skip": 2,
        "max_fps": 15
      }
    }
  ]'
```

### 5. Monitor Events

#### Option A: Using the example consumer script

```bash
python3 example_consumer.py
```

#### Option B: Using Redis CLI directly

```bash
docker exec -it redis redis-cli
> XREAD BLOCK 0 STREAMS stream:events $
```

### 6. View Active Cameras

```bash
curl http://localhost:8069/api/cameras | jq .
```

### 7. Stop a Camera

```bash
curl -X DELETE http://localhost:8069/api/cameras/cam-001
```

## Testing with a Video File

If you don't have an RTSP camera, you can test with a video file:

1. Download a test video:
```bash
wget https://sample-videos.com/video321/mp4/720/big_buck_bunny_720p_1mb.mp4
```

2. Serve it via RTSP using ffmpeg:
```bash
docker run --rm -it -p 8554:8554 \
  -v $(pwd)/big_buck_bunny_720p_1mb.mp4:/video.mp4 \
  bluenviron/mediamtx:latest
```

3. Use the stream URL: `rtsp://localhost:8554/video`

## Common Issues

### Issue: "Failed to connect to Redis"
**Solution:** Make sure Redis container is running on the vms_network:
```bash
docker ps | grep redis
docker network inspect vms_network
```

### Issue: "Failed to open stream"
**Solutions:**
- Verify the RTSP URL is correct and accessible
- Test the stream with VLC or ffplay first
- Check network connectivity
- Ensure the camera is powered on and connected

### Issue: "Model not found"
**Solution:** The YOLO model will be downloaded automatically on first run. Wait for it to complete.

### Issue: High CPU usage
**Solutions:**
- Increase `frame_skip` to 3 or 5
- Reduce `max_fps` to 10 or 15
- Use `yolov8n.pt` (nano model) instead of larger models
- Disable unused detection features

## Monitoring

### View Logs

```bash
# All logs
docker compose logs -f

# Analytics service only
docker compose logs -f analytics-service
```

### Check Redis Stream

```bash
# Replace 'redis' with your Redis container name
docker exec -it redis redis-cli

# Count events
> XLEN stream:events

# View latest events
> XREVRANGE stream:events + - COUNT 10

# View specific event
> XREAD COUNT 1 STREAMS stream:events 0-0
```

## Next Steps

- Check the full [README.md](README.md) for detailed documentation
- Review the [PROJECT_INFO.md](PROJECT_INFO.md) for architecture details
- Customize detection parameters for your use case
- Integrate with your Django application to consume events

## Stopping the Service

```bash
docker compose down
```

To also remove volumes:
```bash
docker compose down -v
```

